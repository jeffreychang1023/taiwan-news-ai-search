# Docker Deployment Best Practices

## Python Version Compatibility

### Critical Lesson from Production (2025-01-20)

**Problem**: Dockerfile used Python 3.13, causing production failure.

**Root Cause**:
- **Dockerfile was using Python 3.13** (lines 2, 20, 44)
- Python 3.13 is too new → qdrant-client installs a broken/incomplete version
- The `AsyncQdrantClient` class existed but was **missing the `search()` method**
- Render logs confirmed: `HAS search: False`, `MODULE FILE: /usr/local/lib/python3.13/site-packages/`
- Local development worked because it was using Python 3.11

### Issue Details

Python 3.13 is too new for many ML/data libraries:
- `qdrant-client` installs but `AsyncQdrantClient` is **missing methods** (e.g., `search()`)
- Other async libraries may have similar incomplete implementations
- Local development may use different Python version → issue only appears in production

### Solution

1. **Use Python 3.11 for production** - mature, stable, broad library support
   ```dockerfile
   FROM python:3.11-slim AS builder       # Line 2 (was 3.13)
   FROM python:3.11-slim                  # Line 20 (was 3.13)
   COPY --from=builder /usr/local/lib/python3.11/site-packages ...  # Line 44
   ```

2. **Pin critical dependencies** - avoid surprises from bleeding-edge versions
   ```
   qdrant-client==1.11.3  # Specific version known to work
   ```

3. **Add runtime diagnostics** - verify environment at startup
   ```python
   # At module load time:
   logger.critical(f"🐍 PYTHON VERSION: {sys.version}")
   logger.critical(f"🔍 MODULE HAS method: {'method' in dir(Module)}")
   ```

4. **Clear Docker build cache** when changing base images
   - Render: "Manual Deploy" → "Clear build cache & deploy"
   - Otherwise old cached layers persist

### Validation

After fixing:
- ✅ Render deployment successful with Python 3.11
- ✅ `AsyncQdrantClient.search()` available
- ✅ Production queries working correctly
- ✅ BM25 and MMR functioning as expected

---

## Debugging Docker Deployment Failures

### When production fails but local works:

1. **Check Python version first** - most common cause of "missing method" errors
2. **Check Docker build logs** - verify correct base image used
3. **Add diagnostic logging** - log versions and available methods at startup
4. **Clear build cache** - force complete rebuild
5. **Check for multiple processes** - old processes may still be running

### Red Flags

- Error: `'ClassName' object has no attribute 'method_name'`
- Library imports but class is incomplete
- Works locally but fails in Docker
- → Likely Python version incompatibility

---

## Key Lessons

1. **Check Python version first** when Docker deployments fail mysteriously
2. **Always clear build cache** when changing base images
3. **Pin dependency versions** to avoid compatibility surprises
4. **Add diagnostic logging at module load** to verify runtime environment
5. **Test with bleeding-edge Python cautiously** - libraries may not be ready

---

## Deployment Checklist

- [ ] Verify Dockerfile uses Python 3.11 (not 3.13)
- [ ] Pin critical dependencies (qdrant-client, etc.)
- [ ] Add runtime diagnostics for key libraries
- [ ] Clear Docker build cache before deploying
- [ ] Test deployment in staging environment first
- [ ] Monitor logs for version/method availability errors
