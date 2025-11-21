from core.state import NLWebHandlerState
import asyncio
from core.prompts import PromptRunner
from misc.logger.logging_config_helper import get_configured_logger

logger = get_configured_logger("post_ranking")


class PostRanking:
    """This class is used to check if any post processing is needed after the ranking is done."""
    
    def __init__(self, handler):
        self.handler = handler

    async def do(self):
        if not self.handler.connection_alive_event.is_set():
            self.handler.query_done = True
            return
        
        # Check if we should send a map message for results with addresses
        await self.check_and_send_map_message()
        
        if (self.handler.generate_mode == "none"):
            # nothing to do
            return
        
        if (self.handler.generate_mode == "summarize"):
            await SummarizeResults(self.handler).do()
            return
    
    async def check_and_send_map_message(self):
        """Check if at least half of the results have addresses and send a map message if so."""
        try:
            # Get the final ranked answers
            results = getattr(self.handler, 'final_ranked_answers', [])
            if not results:
                logger.debug("No results to check for addresses")
                return
            
            # Count results with addresses and collect map data
            results_with_addresses = []
            
            for result in results:
                # Check if result has schema_object field
                if 'schema_object' not in result:
                    continue
                
                schema_obj = result['schema_object']
                
                # Check for address field in schema_object
                address = None
                if isinstance(schema_obj, dict):
                    # Check for different possible address field names
                    address = (schema_obj.get('address') or 
                              schema_obj.get('location') or 
                              schema_obj.get('streetAddress') or
                              schema_obj.get('postalAddress'))
                    
                    # If address is a string, check if it looks like it has a dict representation at the end
                    if isinstance(address, str) and "{" in address:
                        # Extract just the address part before any dictionary representation
                        address = address.split(", {")[0]
                    
                    # If address is a dict, try to get a string representation
                    elif isinstance(address, dict):
                        # Handle structured address
                        address_parts = []
                        for field in ['streetAddress', 'addressLocality', 'addressRegion', 'postalCode']:
                            if field in address:
                                value = address[field]
                                # Skip if it's a dict or complex object
                                if not isinstance(value, dict):
                                    address_parts.append(str(value))
                        
                        # Handle country separately - extract just the name if it's a dict
                        if 'addressCountry' in address:
                            country = address['addressCountry']
                            if isinstance(country, dict) and 'name' in country:
                                address_parts.append(country['name'])
                            elif isinstance(country, str) and not country.startswith('{'):
                                address_parts.append(country)
                        
                        if address_parts:
                            address = ', '.join(address_parts)
                        else:
                            # If we couldn't extract parts, skip this address
                            address = None
                
                if address:
                    results_with_addresses.append({
                        'title': result.get('name', 'Unnamed'),
                        'address': str(address)
                    })
            
            # Check if at least half have addresses
            total_results = len(results)
            results_with_addr_count = len(results_with_addresses)
            
            logger.info(f"Found {results_with_addr_count} results with addresses out of {total_results} total results")
            
            if results_with_addr_count >= total_results / 2 and results_with_addr_count > 0:
                # Send the map message
                map_message = {
                    'message_type': 'results_map',
                    '@type': 'LocationMap',
                    'locations': results_with_addresses
                }
                
                logger.info(f"Sending results_map message with {results_with_addr_count} locations")
                logger.info(f"Map message content: {map_message}")
                
                try:
                    asyncio.create_task(self.handler.send_message(map_message))
                    logger.info("results_map message sent successfully")
                except Exception as e:
                    logger.error(f"Failed to send results_map message: {str(e)}", exc_info=True)
            else:
                logger.debug(f"Not sending map message - only {results_with_addr_count}/{total_results} results have addresses")
                
        except Exception as e:
            logger.error(f"Error checking/sending map message: {str(e)}")
            # Don't fail the whole post-ranking process if map generation fails
            pass
        
       
        
class SummarizeResults(PromptRunner):

    SUMMARIZE_RESULTS_PROMPT_NAME = "SummarizeResultsPrompt"

    def __init__(self, handler):
        super().__init__(handler)

    async def apply_mmr_reranking(self):
        """Apply MMR diversity re-ranking to final_ranked_answers if vectors are available."""
        from core.config import CONFIG

        mmr_enabled = CONFIG.mmr_params.get('enabled', True)
        mmr_threshold = CONFIG.mmr_params.get('threshold', 3)

        # Get ranked results
        ranked = self.handler.final_ranked_answers

        # Check if handler has url_to_vector mapping (from ranking phase)
        url_to_vector = getattr(self.handler, 'url_to_vector', {})

        print(f"[MMR CHECK PostRanking] mmr_enabled={mmr_enabled}, ranked={len(ranked)}, threshold={mmr_threshold}, vectors={len(url_to_vector)}")

        if not mmr_enabled:
            logger.info("MMR disabled in config, using standard ranking")
            return

        if len(ranked) <= mmr_threshold:
            logger.info(f"MMR skipped: only {len(ranked)} results (threshold: {mmr_threshold})")
            return

        if not url_to_vector:
            print(f"[MMR] SKIPPED: no vectors available in PostRanking")
            logger.info("MMR skipped: no vectors available")
            return

        logger.info(f"[MMR PostRanking] Applying diversity re-ranking to {len(ranked)} results")

        # Attach vectors to ranked results
        for result in ranked:
            url = result.get('url', '')
            if url in url_to_vector:
                result['vector'] = url_to_vector[url]

        # Apply MMR
        from core.mmr import MMRReranker
        mmr_lambda = CONFIG.mmr_params.get('lambda', 0.7)
        mmr_reranker = MMRReranker(lambda_param=mmr_lambda, query=self.handler.query)

        # Get top_k from config or use default
        top_k = len(ranked)  # Re-rank all results

        reranked_results, mmr_scores = mmr_reranker.rerank(
            ranked_results=ranked,
            top_k=top_k
        )

        # Log MMR scores to analytics
        from core.query_logger import get_query_logger
        query_logger = get_query_logger()
        if hasattr(self.handler, 'query_id'):
            for idx, (result, mmr_score) in enumerate(zip(reranked_results, mmr_scores)):
                url = result.get('url', '')
                query_logger.log_mmr_score(
                    query_id=self.handler.query_id,
                    doc_url=url,
                    mmr_score=mmr_score,
                    ranking_position=idx
                )

        # Update handler's final ranked answers
        self.handler.final_ranked_answers = reranked_results
        logger.info(f"[MMR PostRanking] Re-ranking complete: {len(reranked_results)} diverse results")

        # Clean up: Remove vectors from results before passing to LLM prompts
        # Vectors are 1536 floats and will pollute the prompt output
        for result in self.handler.final_ranked_answers:
            result.pop('vector', None)

    async def do(self):
        # MMR diversity re-ranking is already done in ranking.py
        # No need to apply it again here - would be redundant
        # await self.apply_mmr_reranking()  # REMOVED: duplicate MMR call

        # Use ALL the final ranked answers that are shown in list view
        # Don't limit to 3 - use the same results shown to the user
        # self.handler.final_ranked_answers = self.handler.final_ranked_answers[:3]  # OLD: only used 3
        response = await self.run_prompt(self.SUMMARIZE_RESULTS_PROMPT_NAME, timeout=20, max_length=1024)
        if (not response):
            return
        self.handler.summary = response["summary"]
        message = {"message_type": "result", "@type": "Summary", "content": self.handler.summary}
        asyncio.create_task(self.handler.send_message(message))
        # Use proper state update
        await self.handler.state.precheck_step_done("post_ranking")
