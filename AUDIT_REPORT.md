# Dashboard Audit Report

**Date:** 2026-01-05
**Auditor:** Claude
**Branch:** claude/audit-dashboard-IYQFP

---

## Executive Summary

The China Snapshot Dashboard is a well-architected serverless application for monitoring real-time China signals. The codebase demonstrates good security practices, proper error handling, and a clean separation of concerns. However, several areas need attention.

**Overall Assessment:** Good with minor improvements needed

| Category | Rating | Notes |
|----------|--------|-------|
| Security | B+ | Good practices, minor gaps |
| Code Quality | A- | Clean, consistent patterns |
| Reliability | B+ | Solid error handling, some edge cases |
| Maintainability | B | Good structure, limited tests |
| Performance | A- | Efficient, smart refresh logic |

---

## Findings

### Critical Issues (0)

No critical security vulnerabilities or blocking issues found.

### High Priority Issues (2)

#### 1. Legacy `/data/` Directory Contains Stale Files
**Location:** `/data/`
**Risk:** Medium - Confusion and potential data inconsistency

The project has a legacy `/data/` directory containing old JSON files:
- `baidu_top.json` (empty/stale)
- `weibo_hot.json` (empty/stale)
- `indices.json` (outdated)
- `fx.json` (outdated)

Active data is stored in `/docs/data/`. The legacy directory should be removed.

**Recommendation:** Delete the `/data/` directory and its contents (except `.gitkeep` if needed).

#### 2. XSS Vulnerability in Indices/FX Rendering
**Location:** `docs/app.js:1147-1163`
**Risk:** Medium - Potential XSS if external data is compromised

The `render()` function uses `innerHTML` for indices and FX data:
```javascript
li.innerHTML = `<a href="${item.url}"...>${item.title}</a>...`;
```

While external API data is generally trusted, this pattern could be exploited if the upstream API is compromised.

**Recommendation:** Use `textContent` and DOM methods like the news sections do.

---

### Medium Priority Issues (5)

#### 3. Missing Test Coverage
**Location:** Project-wide
**Risk:** Low - Reduces confidence in changes

No test files were found in the codebase. The `tests/` directory mentioned in documentation appears to be empty or non-existent.

**Recommendation:** Add unit tests for:
- `collectors/common.py` utilities
- JSON schema validation
- Translation function edge cases

#### 4. Hardcoded Configuration Values
**Location:** Multiple collectors
**Risk:** Low - Maintenance burden

Configuration is scattered across files:
- `app.js:212` - `HEADLINE_LIMIT = 5`
- `ladymax.py` - `MAX_ITEMS = 21`
- Various collectors have different item limits

**Recommendation:** Centralize configuration in a single config file or environment variables.

#### 5. Indices Collector Missing History Support
**Location:** `collectors/indices_cn.py:74`
**Risk:** Low - Inconsistent data retention

Uses `write_json()` instead of `write_with_history()`, meaning no historical snapshots are preserved for market data.

**Recommendation:** Add history support for indices data like other collectors.

#### 6. FX Collector Missing History Support
**Location:** `collectors/fx_cny.py`
**Risk:** Low - Inconsistent data retention

Same issue as indices - no historical data preserved.

**Recommendation:** Add history support for FX data.

#### 7. Weather Collector Missing History Support
**Location:** `collectors/weather_cn.py`
**Risk:** Low - Inconsistent data retention

Same issue - weather data has no historical tracking.

**Recommendation:** Consider if weather history is valuable; if so, add support.

---

### Low Priority Issues (6)

#### 8. Unused CSS Selectors
**Location:** `docs/styles.css:857-863`
**Description:** Uses `:has-text()` pseudo-selector which isn't standard CSS

```css
.data-list .muted:has-text("▲") {
  color: var(--color-success);
}
```

This selector doesn't work in browsers. The percentage color coding for positive/negative values isn't functional.

**Recommendation:** Implement via JavaScript class toggling instead.

#### 9. OpenAI Client Recreated Per Translation
**Location:** `collectors/common.py:191`
**Description:** Creates new `OpenAI()` client for each translation call

This is inefficient for batch translations.

**Recommendation:** Consider creating client once per collector run.

#### 10. Commit Email Uses Placeholder
**Location:** `.github/workflows/collect.yml:105`
**Description:** Uses `bot@example.com` which isn't a real email

**Recommendation:** Use a proper noreply email like `china-snapshot-bot@users.noreply.github.com`

#### 11. No Rate Limit Handling for OpenAI
**Location:** `collectors/common.py:183-234`
**Description:** No specific handling for OpenAI rate limits (429 errors)

The retry logic handles general errors but doesn't specifically handle rate limiting with appropriate backoff.

**Recommendation:** Add rate limit detection and longer backoff.

#### 12. `html2text` Version Pinning Issue
**Location:** `requirements.txt:8`
**Description:** Pins to `>=2025.4.15` which is a future date

```
html2text>=2025.4.15
```

This version doesn't exist yet (current date is 2026-01-05, but this version format seems unusual).

**Recommendation:** Verify this is the correct version specifier.

#### 13. Missing `rel="noreferrer"` on External Links
**Location:** `docs/app.js` (multiple locations)
**Description:** External links use `rel="noopener"` but not `noreferrer`

While `noopener` prevents the new page from accessing `window.opener`, adding `noreferrer` also prevents the `Referer` header from being sent.

**Recommendation:** Add `noreferrer` to external links: `rel="noopener noreferrer"`

---

## Security Analysis

### Strengths

1. **Path Traversal Protection** (`common.py:35-43`)
   - Validates all output paths against allowed directories
   - Prevents writing outside `/docs/data/`

2. **File Size Limits** (`common.py:46-48`)
   - Enforces 10MB maximum file size
   - Prevents DoS via large payloads

3. **API Key Protection** (`common.py:226`)
   - Sanitizes API keys from error messages
   - Prevents accidental exposure in logs

4. **XSS Prevention** (partial)
   - News sections use `textContent` for user-generated content
   - Links properly use `target="_blank"` with `rel="noopener"`

5. **Atomic File Writes** (`common.py:154-167`)
   - Uses temp file + rename pattern
   - Prevents partial writes on failures

6. **No Secrets in Repository**
   - All API keys stored in GitHub Secrets
   - `.env.example` contains only placeholders

### Recommendations for Improvement

1. Add Content Security Policy (CSP) headers (would require server config for GitHub Pages)
2. Consider Subresource Integrity (SRI) for external fonts
3. Add input validation for fetched content before display

---

## Architecture Review

### Data Flow
```
External APIs → Python Collectors → JSON Files → GitHub Pages → Browser
```

The architecture is sound for the use case. The serverless design eliminates infrastructure maintenance while GitHub Actions provides reliable automation.

### Frontend Architecture
- Single-page application with vanilla JavaScript
- Smart refresh mechanism (HEAD requests for change detection)
- Theme switching with localStorage persistence
- History navigation for trending data
- Live ticker with multiple sources

### Backend Architecture
- 9 independent Python collectors
- Shared utilities in `common.py`
- Graceful degradation when APIs fail
- Health monitoring with status badges

---

## Files Reviewed

| File | Lines | Assessment |
|------|-------|------------|
| `docs/index.html` | 193 | Good - Semantic HTML, accessible |
| `docs/app.js` | 1549 | Good - Clean patterns, minor XSS risk |
| `docs/styles.css` | 1118 | Good - Well-organized, one dead selector |
| `collectors/common.py` | 235 | Good - Strong security practices |
| `collectors/xinhua_rss.py` | 161 | Good - Proper error handling |
| `collectors/baidu_top.py` | 267 | Good - Flexible API parsing |
| `collectors/indices_cn.py` | 79 | OK - Missing history support |
| `.github/workflows/collect.yml` | 146 | Good - Robust with retry logic |
| `requirements.txt` | 8 | OK - Version pinning issue |

---

## Recommendations Summary

### Immediate Actions
1. Remove legacy `/data/` directory
2. Fix innerHTML usage in indices/FX rendering

### Short-term Improvements
1. Add basic unit tests
2. Add history support for all collectors
3. Centralize configuration

### Long-term Enhancements
1. Add rate limit handling for OpenAI
2. Consider caching translations
3. Add monitoring/alerting for collector failures

---

## Conclusion

The China Snapshot Dashboard is a well-built application with solid security practices and clean code. The main areas for improvement are:

1. Cleaning up legacy files
2. Fixing the minor XSS vulnerability in index/FX rendering
3. Adding test coverage
4. Standardizing history support across all collectors

The codebase is production-ready with these minor improvements.
