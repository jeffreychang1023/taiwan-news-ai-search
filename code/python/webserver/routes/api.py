"""Core API routes for aiohttp server"""

from aiohttp import web
import asyncio
import logging
import json
import os
import time as time_mod
from typing import Dict, Any
from core.whoHandler import WhoHandler
from methods.generate_answer import GenerateAnswer
from webserver.aiohttp_streaming_wrapper import AioHttpStreamingWrapper
from core.retriever import get_vector_db_client
from core.utils.utils import get_param
from core.config import CONFIG
from webserver.middleware.rate_limit import _get_client_ip
from core.query_analysis.query_sanitizer import MAX_QUERY_LENGTH
from webserver.middleware.concurrency_limiter import (
    ConcurrencyLimiter,
    SEARCH_SESSION_LIMIT,
    SEARCH_IP_LIMIT,
    DR_USER_LIMIT,
    DR_IP_LIMIT,
)

logger = logging.getLogger(__name__)


def setup_api_routes(app: web.Application):
    """Setup core API routes"""
    # Query endpoints
    app.router.add_get('/ask', ask_handler)
    app.router.add_post('/ask', ask_handler)
    app.router.add_get('/api/deep_research', deep_research_handler)
    app.router.add_post('/api/deep_research', deep_research_handler)

    # Feedback endpoint
    app.router.add_post('/api/feedback', feedback_handler)

    # Info endpoints
    app.router.add_get('/who', who_handler)
    app.router.add_get('/sites', sites_handler)
    app.router.add_get('/sites_config', sites_config_handler)


async def ask_handler(request: web.Request) -> web.Response:
    """Handle /ask endpoint for generating answers"""
    
    # Get query parameters
    query_params = dict(request.query)
    
    # For POST requests, merge body parameters
    if request.method == 'POST':
        try:
            if request.content_type == 'application/json':
                body_data = await request.json()
                query_params.update(body_data)
            elif request.content_type == 'application/x-www-form-urlencoded':
                body_data = await request.post()
                query_params.update(dict(body_data))
        except Exception as e:
            logger.warning(f"Failed to parse POST body: {e}")
    
    # Inject auth user info into query_params (overrides query param spoofing)
    user = request.get('user')
    if user and user.get('authenticated'):
        query_params['user_id'] = user['id']
        if user.get('org_id'):
            query_params['org_id'] = user['org_id']

    # P1-2: Query length pre-check (before SSE stream starts — must return HTTP 400 JSON)
    query = query_params.get('query', '')
    if len(query) > MAX_QUERY_LENGTH:
        client_ip = _get_client_ip(request)
        user = request.get('user')
        uid = user.get('id') if user and user.get('authenticated') else None
        try:
            from core.guardrail_logger import GuardrailLogger
            await GuardrailLogger.get_instance().log_event(
                event_type='query_rejected',
                severity='info',
                user_id=uid,
                client_ip=client_ip,
                details={'reason': 'query_too_long', 'length': len(query)},
            )
        except Exception as _log_err:
            logger.warning(f"GuardrailLogger failed in ask_handler: {_log_err}")
        return web.json_response(
            {'error': 'query_too_long', 'message': '查詢過長，請縮短至 500 字元以內'},
            status=400,
        )

    # P1-1b: General search concurrency check
    client_ip = _get_client_ip(request)
    user = request.get('user')
    uid = user.get('id') if user and user.get('authenticated') else None
    request_id = f"req_{int(time_mod.time() * 1000)}_{id(request)}"
    session_id = query_params.get('session_id') or uid or client_ip

    if uid:
        conc_key = f"search:{session_id}"
        conc_limit = SEARCH_SESSION_LIMIT
    else:
        conc_key = f"search_ip:{client_ip}"
        conc_limit = SEARCH_IP_LIMIT

    limiter = ConcurrencyLimiter.get_instance()
    if not limiter.try_acquire(conc_key, request_id, conc_limit):
        try:
            from core.guardrail_logger import GuardrailLogger
            await GuardrailLogger.get_instance().log_event(
                event_type='concurrency_limit',
                severity='warning',
                user_id=uid,
                client_ip=client_ip,
                details={'key': conc_key, 'limit': conc_limit},
            )
        except Exception as _log_err:
            logger.warning(f"GuardrailLogger failed (concurrency): {_log_err}")
        return web.json_response(
            {'error': 'rate_limited', 'message': '目前查詢量過大，請稍後再試', 'retry_after_seconds': 30},
            status=429,
        )

    # Check if SSE streaming is requested
    is_sse = request.get('is_sse', False)
    streaming = get_param(query_params, "streaming", str, "True")
    streaming = streaming not in ["False", "false", "0"]

    dr_key = None
    dr_request_id = None
    try:
        # P1-1b: DR concurrency check for /ask?generate_mode=deep_research
        generate_mode = query_params.get('generate_mode', 'none')
        if generate_mode == 'deep_research':
            # Kill switch
            if os.environ.get('GUARDRAIL_DR_ENABLED', 'true').lower() == 'false':
                return web.json_response(
                    {'error': 'dr_disabled', 'message': 'Deep Research 功能暫時關閉'},
                    status=503,
                )
            if uid:
                dr_key = f"dr_user:{uid}"
                dr_limit = DR_USER_LIMIT
            else:
                dr_key = f"dr_ip:{client_ip}"
                dr_limit = DR_IP_LIMIT
            dr_request_id = f"dr_{request_id}"
            if not limiter.try_acquire(dr_key, dr_request_id, dr_limit):
                try:
                    from core.guardrail_logger import GuardrailLogger
                    await GuardrailLogger.get_instance().log_event(
                        event_type='concurrency_limit',
                        severity='warning',
                        user_id=uid,
                        client_ip=client_ip,
                        details={'key': dr_key, 'limit': dr_limit, 'reason': 'dr_concurrency'},
                    )
                except Exception as _log_err:
                    logger.warning(f"GuardrailLogger failed (DR concurrency): {_log_err}")
                return web.json_response(
                    {'error': 'rate_limited', 'message': 'Deep Research 同時只能進行一個，請等待完成後再試', 'retry_after_seconds': 30},
                    status=429,
                )

        if is_sse or streaming:
            return await handle_streaming_ask(request, query_params)
        else:
            return await handle_regular_ask(request, query_params)
    finally:
        # Always release slots — even if request crashes
        limiter.release(conc_key, request_id)
        if dr_key and dr_request_id:
            limiter.release(dr_key, dr_request_id)


async def handle_streaming_ask(request: web.Request, query_params: Dict[str, Any]) -> web.StreamResponse:
    """Handle streaming (SSE) ask requests"""
    
    # Create SSE response
    response = web.StreamResponse(
        status=200,
        headers={
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )
    
    await response.prepare(request)
    
    # Create aiohttp-compatible wrapper
    wrapper = AioHttpStreamingWrapper(request, response, query_params)
    await wrapper.prepare_response()
    
    try:
        # Determine which handler to use based on generate_mode
        generate_mode = query_params.get('generate_mode', 'none')

        if generate_mode == 'generate':
            handler = GenerateAnswer(query_params, wrapper)
            wrapper.set_on_disconnect(lambda: handler.connection_alive_event.clear())
            await handler.runQuery()
        elif generate_mode == 'deep_research':
            # Deep research mode with multi-agent reasoning
            from methods.deep_research import DeepResearchHandler
            handler = DeepResearchHandler(query_params, wrapper)
            wrapper.set_on_disconnect(lambda: handler.connection_alive_event.clear())
            await handler.runQuery()
        elif generate_mode == 'unified':
            # Unified mode: single SSE stream for articles + summary + AI answer
            unified_start_time = time_mod.time()
            unified_error = False

            from core.baseHandler import NLWebHandler
            handler = NLWebHandler(query_params, wrapper)
            wrapper.set_on_disconnect(lambda: handler.connection_alive_event.clear())
            handler.skip_end_response = True  # api.py controls end timing

            try:
                await handler.runQuery()  # retrieval + ranking + PostRanking

                await asyncio.sleep(0)  # flush pending create_tasks

                # Check connection before synthesis
                if not handler.connection_alive_event.is_set():
                    logger.info("Client disconnected before synthesis, skipping")
                else:
                    # Inject conversation_id into query_params for GenerateAnswer (Issue #2)
                    query_params['conversation_id'] = handler.conversation_id
                    gen_handler = GenerateAnswer(query_params, wrapper)

                    # Inject state from first handler
                    gen_handler.final_ranked_answers = handler.final_ranked_answers
                    gen_handler.items = [
                        [r.get('url', ''), json.dumps(r.get('schema_object', {})), r.get('name', ''), r.get('site', '')]
                        for r in handler.final_ranked_answers
                    ]
                    gen_handler.decontextualized_query = handler.decontextualized_query
                    gen_handler.connection_alive_event = handler.connection_alive_event
                    gen_handler.query_id = handler.query_id  # Issue #3: same query

                    await gen_handler.synthesizeAnswer()
            except Exception as e:
                unified_error = True
                logger.error(f"Error in unified mode: {e}", exc_info=True)
            finally:
                # Always send end response (api.py controls timing)
                await handler.message_sender.send_end_response(error=unified_error)

            # Issue #4: Log unified analytics with full latency
            try:
                unified_total_ms = (time_mod.time() - unified_start_time) * 1000
                from core.query_logger import get_query_logger
                query_logger = get_query_logger()
                num_results = len(handler.final_ranked_answers) if hasattr(handler, 'final_ranked_answers') else 0
                query_logger.log_query_complete(
                    query_id=handler.query_id,
                    latency_total_ms=unified_total_ms,
                    num_results_retrieved=getattr(handler, 'num_retrieved', 0),
                    num_results_ranked=getattr(handler, 'num_ranked', 0),
                    num_results_returned=num_results,
                    cost_usd=getattr(handler, 'estimated_cost', 0),
                    error_occurred=unified_error
                )
            except Exception as e:
                logger.warning(f"Failed to log unified analytics: {e}")
        else:
            # Use base NLWebHandler for other modes (summarize, none)
            from core.baseHandler import NLWebHandler
            handler = NLWebHandler(query_params, wrapper)
            wrapper.set_on_disconnect(lambda: handler.connection_alive_event.clear())
            await handler.runQuery()
        
        # Send completion message
        await wrapper.write_stream({"message_type": "complete", "sender_info": {"id": "system", "name": "NLWeb"}})
        
    except Exception as e:
        import traceback; traceback.print_exc()  # DEBUG: print full traceback to stderr
        logger.error(f"Error in streaming ask handler: {e}", exc_info=True)
        await wrapper.send_error_response(500, str(e))
    finally:
        await wrapper.finish_response()
    
    return response


async def handle_regular_ask(request: web.Request, query_params: Dict[str, Any]) -> web.Response:
    """Handle non-streaming ask requests"""
    
    try:
        # Determine which handler to use
        generate_mode = query_params.get('generate_mode', 'none')

        if generate_mode == 'generate':
            handler = GenerateAnswer(query_params, None)
        elif generate_mode == 'deep_research':
            # Deep research mode with multi-agent reasoning
            from methods.deep_research import DeepResearchHandler
            handler = DeepResearchHandler(query_params, None)
        else:
            # Use base NLWebHandler for other modes (summarize, none)
            from core.baseHandler import NLWebHandler
            handler = NLWebHandler(query_params, None)
        
        # Run the query - it will return the complete response
        result = await handler.runQuery()
        
        # Return the response directly
        return web.json_response(result)
        
    except Exception as e:
        logger.error(f"Error in regular ask handler: {e}", exc_info=True)
        return web.json_response({
            "message_type": "error",
            "error": str(e)
        }, status=500)


async def who_handler(request: web.Request) -> web.Response:
    """Handle /who endpoint with optional streaming support"""
    
    try:
        # Get query parameters
        query_params = dict(request.query)
        
        # Check if SSE streaming is requested
        is_sse = request.get('is_sse', False)
        streaming = get_param(query_params, "streaming", str, "False")
        streaming = streaming not in ["False", "false", "0"]
        
        if is_sse or streaming:
            # Handle streaming response
            response = web.StreamResponse(
                status=200,
                headers={
                    'Content-Type': 'text/event-stream',
                    'Cache-Control': 'no-cache',
                    'Connection': 'keep-alive',
                    'X-Accel-Buffering': 'no'
                }
            )
            
            await response.prepare(request)
            
            # Create aiohttp-compatible wrapper
            wrapper = AioHttpStreamingWrapper(request, response, query_params)
            await wrapper.prepare_response()
            
            try:
                # Run the who handler with streaming
                handler = WhoHandler(query_params, wrapper)
                await handler.runQuery()
                
                # Send completion message
                await wrapper.write_stream({"message_type": "complete", "sender_info": {"id": "system", "name": "NLWeb"}})
                
            except Exception as e:
                logger.error(f"Error in streaming who handler: {e}", exc_info=True)
                await wrapper.send_error_response(500, str(e))
            finally:
                await wrapper.finish_response()
            
            return response
        else:
            # Handle non-streaming response
            handler = WhoHandler(query_params, None)
            result = await handler.runQuery()
            return web.json_response(result)
        
    except Exception as e:
        logger.error(f"Error in who handler: {e}", exc_info=True)
        return web.json_response({
            "message_type": "error",
            "error": str(e)
        }, status=500)


async def sites_handler(request: web.Request) -> web.Response:
    """Handle /sites endpoint to get available sites"""
    
    try:
        # Get query parameters
        query_params = dict(request.query)
        
        # Check if streaming is requested
        streaming = get_param(query_params, "streaming", str, "False")
        streaming = streaming not in ["False", "false", "0"]
        
        # Create a retriever client
        retriever = get_vector_db_client(query_params=query_params)
        
        # Get the list of sites
        sites = await retriever.get_sites()
        
        # Prepare the response
        response_data = {
            "message-type": "sites",
            "sites": sites
        }
        
        if streaming or request.get('is_sse', False):
            # Return as SSE
            response = web.StreamResponse(
                status=200,
                headers={
                    'Content-Type': 'text/event-stream',
                    'Cache-Control': 'no-cache',
                    'Connection': 'keep-alive',
                    'X-Accel-Buffering': 'no'
                }
            )
            await response.prepare(request)
            await response.write(f"data: {json.dumps(response_data)}\n\n".encode())
            return response
        else:
            # Return as JSON
            return web.json_response(response_data)
            
    except Exception as e:
        logger.error(f"Error getting sites: {e}", exc_info=True)
        error_data = {
            "message-type": "error",
            "error": f"Failed to get sites: {str(e)}"
        }
        return web.json_response(error_data, status=500)


async def sites_config_handler(request: web.Request) -> web.Response:
    """Handle /sites_config endpoint to get site configurations from sites.xml"""

    try:
        # Get site configs from CONFIG (loaded from sites.xml)
        site_configs = {}
        if hasattr(CONFIG, 'nlweb') and hasattr(CONFIG.nlweb, 'site_configs'):
            site_configs = CONFIG.nlweb.site_configs

        # Convert to list format for frontend
        sites_list = []
        for site_name, config in site_configs.items():
            sites_list.append({
                "name": site_name,
                "description": config.description,
                "item_types": config.item_types
            })

        # Sort by name
        sites_list.sort(key=lambda x: x["name"])

        response_data = {
            "message_type": "sites_config",
            "sites": sites_list
        }

        return web.json_response(response_data)

    except Exception as e:
        logger.error(f"Error getting sites config: {e}", exc_info=True)
        return web.json_response({
            "message_type": "error",
            "error": f"Failed to get sites config: {str(e)}"
        }, status=500)


async def deep_research_handler(request: web.Request) -> web.Response:
    """Handle /api/deep_research endpoint for Deep Research mode with SSE streaming"""

    # Get query parameters
    query_params = dict(request.query)

    # For POST requests, merge body parameters
    if request.method == 'POST':
        try:
            if request.content_type == 'application/json':
                body_data = await request.json()
                query_params.update(body_data)
            elif request.content_type == 'application/x-www-form-urlencoded':
                body_data = await request.post()
                query_params.update(dict(body_data))
        except Exception as e:
            logger.warning(f"Failed to parse POST body: {e}")

    # Force Deep Research mode
    query_params['generate_mode'] = 'deep_research'
    query_params['streaming'] = 'true'  # Always use streaming for Deep Research

    # Extract query
    query = get_param(query_params, "query", str, "")
    if not query:
        return web.json_response({
            "message_type": "error",
            "error": "Missing query parameter"
        }, status=400)

    # P1-2: Query length pre-check (before SSE stream starts — must return HTTP 400 JSON)
    if len(query) > MAX_QUERY_LENGTH:
        client_ip = _get_client_ip(request)
        user = request.get('user')
        uid = user.get('id') if user and user.get('authenticated') else None
        try:
            from core.guardrail_logger import GuardrailLogger
            await GuardrailLogger.get_instance().log_event(
                event_type='query_rejected',
                severity='info',
                user_id=uid,
                client_ip=client_ip,
                details={'reason': 'query_too_long', 'length': len(query)},
            )
        except Exception as _log_err:
            logger.warning(f"GuardrailLogger failed in deep_research_handler: {_log_err}")
        return web.json_response(
            {'error': 'query_too_long', 'message': '查詢過長，請縮短至 500 字元以內'},
            status=400,
        )

    logger.info(f"Deep Research request: {query}")

    # P1-1b: Kill switch
    if os.environ.get('GUARDRAIL_DR_ENABLED', 'true').lower() == 'false':
        return web.json_response(
            {'error': 'dr_disabled', 'message': 'Deep Research 功能暫時關閉'},
            status=503,
        )

    # P1-1b: Concurrency checks — general search slot + DR-specific slot
    dr_client_ip = _get_client_ip(request)
    dr_user = request.get('user')
    dr_uid = dr_user.get('id') if dr_user and dr_user.get('authenticated') else None
    dr_request_id = f"req_{int(time_mod.time() * 1000)}_{id(request)}"
    dr_session_id = query_params.get('session_id') or dr_uid or dr_client_ip

    if dr_uid:
        dr_search_key = f"search:{dr_session_id}"
        dr_search_limit = SEARCH_SESSION_LIMIT
    else:
        dr_search_key = f"search_ip:{dr_client_ip}"
        dr_search_limit = SEARCH_IP_LIMIT

    if dr_uid:
        dr_conc_key = f"dr_user:{dr_uid}"
        dr_conc_limit = DR_USER_LIMIT
    else:
        dr_conc_key = f"dr_ip:{dr_client_ip}"
        dr_conc_limit = DR_IP_LIMIT

    dr_limiter = ConcurrencyLimiter.get_instance()
    dr_search_acquired = False
    dr_slot_acquired = False

    # Acquire general search slot
    if not dr_limiter.try_acquire(dr_search_key, dr_request_id, dr_search_limit):
        try:
            from core.guardrail_logger import GuardrailLogger
            await GuardrailLogger.get_instance().log_event(
                event_type='concurrency_limit',
                severity='warning',
                user_id=dr_uid,
                client_ip=dr_client_ip,
                details={'key': dr_search_key, 'limit': dr_search_limit},
            )
        except Exception as _log_err:
            logger.warning(f"GuardrailLogger failed (DR search concurrency): {_log_err}")
        return web.json_response(
            {'error': 'rate_limited', 'message': '目前查詢量過大，請稍後再試', 'retry_after_seconds': 30},
            status=429,
        )
    dr_search_acquired = True

    # Acquire DR-specific slot
    dr_slot_id = f"dr_{dr_request_id}"
    if not dr_limiter.try_acquire(dr_conc_key, dr_slot_id, dr_conc_limit):
        dr_limiter.release(dr_search_key, dr_request_id)
        try:
            from core.guardrail_logger import GuardrailLogger
            await GuardrailLogger.get_instance().log_event(
                event_type='concurrency_limit',
                severity='warning',
                user_id=dr_uid,
                client_ip=dr_client_ip,
                details={'key': dr_conc_key, 'limit': dr_conc_limit, 'reason': 'dr_concurrency'},
            )
        except Exception as _log_err:
            logger.warning(f"GuardrailLogger failed (DR concurrency): {_log_err}")
        return web.json_response(
            {'error': 'rate_limited', 'message': 'Deep Research 同時只能進行一個，請等待完成後再試', 'retry_after_seconds': 30},
            status=429,
        )
    dr_slot_acquired = True

    try:
        # Create SSE response with proper headers
        response = web.StreamResponse(
            status=200,
            reason='OK',
            headers={
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no'
            }
        )
        await response.prepare(request)

        # Create streaming wrapper
        wrapper = AioHttpStreamingWrapper(request, response, query_params)
        await wrapper.prepare_response()

        # Import and create Deep Research handler
        from methods.deep_research import DeepResearchHandler
        handler = DeepResearchHandler(query_params, wrapper)
        wrapper.set_on_disconnect(lambda: handler.connection_alive_event.clear())

        # Send begin-nlweb-response so frontend can capture conversation_id
        begin_message = {
            "message_type": "begin-nlweb-response",
            "query": query,
            "conversation_id": handler.conversation_id
        }
        await wrapper.write_stream(begin_message)
        logger.info(f"[Deep Research] Sent begin-nlweb-response with conversation_id={handler.conversation_id}")

        # Run Deep Research query (will stream progress via SSE)
        result = await handler.runQuery()

        # Send final result message (skip if clarification is pending)
        if result and result.get('status') != 'clarification_pending':
            final_message = {
                "message_type": "final_result",
                "final_report": result.get('answer', ''),
                "confidence_level": result.get('confidence_level', 'Medium'),
                "methodology": result.get('methodology_note', ''),
                "sources": result.get('sources_used', [])
            }

            # Extract argument_graph and reasoning_chain_analysis from schema_object (Phase 4)
            # These are stored in the first item's schema_object by the orchestrator
            items = result.get('items', [])
            if items and len(items) > 0:
                schema_obj = items[0].get('schema_object', {})
                if schema_obj.get('argument_graph'):
                    final_message['argument_graph'] = schema_obj['argument_graph']
                if schema_obj.get('reasoning_chain_analysis'):
                    final_message['reasoning_chain_analysis'] = schema_obj['reasoning_chain_analysis']
                if schema_obj.get('knowledge_graph'):
                    final_message['knowledge_graph'] = schema_obj['knowledge_graph']
                # RSN-4: Include verification status for frontend warning banner
                if schema_obj.get('verification_status'):
                    final_message['verification_status'] = schema_obj['verification_status']
                if schema_obj.get('verification_message'):
                    final_message['verification_message'] = schema_obj['verification_message']

            await wrapper.write_stream(final_message)

            # Note: Research report is now passed directly from frontend to backend
            # via query_params in free conversation mode, no DB storage needed

        # Close the stream
        await wrapper.write_stream({"message_type": "complete"})
        await wrapper.finish_response()

        return response

    except ConnectionResetError as e:
        logger.info(f"Deep Research client disconnected: {e}")
        try:
            await wrapper.finish_response()
        except Exception:
            pass
        return response

    except Exception as e:
        logger.error(f"Deep Research error: {e}", exc_info=True)
        error_data = {
            "message_type": "error",
            "error": str(e)
        }
        try:
            await wrapper.write_stream(error_data)
            await wrapper.finish_response()
        except Exception:
            pass
        return response

    finally:
        # Always release concurrency slots — even if request crashes
        if dr_search_acquired:
            dr_limiter.release(dr_search_key, dr_request_id)
        if dr_slot_acquired:
            dr_limiter.release(dr_conc_key, dr_slot_id)


async def feedback_handler(request: web.Request) -> web.Response:
    """Handle POST /api/feedback — store user feedback (thumbs up/down + comment)."""
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    rating = body.get("rating", "")
    if rating not in ("positive", "negative"):
        return web.json_response({"error": "rating must be 'positive' or 'negative'"}, status=400)

    query = body.get("query", "")
    answer_snippet = body.get("answer_snippet", "")
    comment = body.get("comment", "")[:2000] if body.get("comment") else ""
    session_id = body.get("session_id", "")
    query_id = body.get("query_id") or None

    # Extract authenticated user info for B2B analytics
    auth_user = request.get('user') or {}
    feedback_user_id = auth_user.get('id') if auth_user.get('authenticated') else None
    feedback_org_id = auth_user.get('org_id') if auth_user.get('authenticated') else None

    try:
        from core.query_logger import get_query_logger
        ql = get_query_logger()
        ql.log_feedback(
            query=query,
            answer_snippet=answer_snippet,
            rating=rating,
            comment=comment,
            session_id=session_id,
            query_id=query_id,
            user_id=feedback_user_id,
            org_id=feedback_org_id,
        )
        logger.info(f"[Feedback] Stored: rating={rating}, query='{query[:50]}'")
        return web.json_response({"status": "ok"})
    except Exception as e:
        logger.error(f"[Feedback] Failed to store feedback: {e}", exc_info=True)
        return web.json_response({"error": "Failed to store feedback"}, status=500)

