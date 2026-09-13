# PawReach Security & Dependency Vulnerability Audit

**Audit Date**: September 13, 2026  
**Phase**: MVP Phase 2.9 — Staging Deployment & Pilot Certification  
**Target Goal**: 0 High or Critical npm vulnerabilities  
**Audit Result**: **0 High, 0 Critical, 0 Moderate, 0 Low vulnerabilities**

---

## 1. Executive Summary

Prior to Phase 2.9, automated CI dependency checks reported a high-severity vulnerability and multiple moderate vulnerabilities stemming from the transitive dependency `undici` introduced by the Google Firebase client SDK (`@firebase/auth`, `@firebase/firestore`, `@firebase/functions`, `@firebase/storage`).

Following a deep dependency path analysis, a surgical npm override was implemented in `frontend/package.json` to pin `undici` to safe version `^6.28.1` without forcing breaking major package upgrades or disrupting compatibility with React 19, Vite, Firebase, Leaflet, or Recharts.

---

## 2. Vulnerability Details (Before Mitigation)

| Package | Severity | Advisory IDs / CVEs | Dependency Path | Version Before |
|---|---|---|---|---|
| **undici** | **High** | GHSA-c76h-2ccp-4975, GHSA-g9mf-h72j-4rw9, GHSA-cxrh-j4jr-qwg3, GHSA-f269-vfmq-vjvj, GHSA-2mjp-6q6p-2qxm, GHSA-vrm6-8vpv-qv8q, GHSA-v9p9-hfj2-hcw8, GHSA-4992-7rv2-5pvq, GHSA-p88m-4jfj-68fv, GHSA-vxpw-j846-p89q, GHSA-g8m3-5g58-fq7m, GHSA-8xcm-r25x-g524, GHSA-m8rv-5g2x-5cg5, GHSA-v3r7-h72x-cjcm, GHSA-35p6-xmwp-9g52 | `frontend` $\to$ `firebase@10.8.0` $\to$ `@firebase/auth@1.7.9` $\to$ `undici@<=6.27.0` | `<=6.27.0` |

### Description & Impact
- Insufficiently random values in `undici` when creating HTTP/WebSocket clients.
- Unbounded decompression chain in HTTP responses via `Content-Encoding` leading to potential resource exhaustion (DoS).
- CRLF injection and HTTP request/response smuggling vectors in `undici` HTTP clients.
- WebSocket permessage-deflate unbounded memory consumption.

---

## 3. Mitigation Strategy

### Evaluated Alternatives
1. **Blind `npm audit fix --force`**: **REJECTED**. Upgrades dependencies across breaking major versions, breaking React 19 compatibility and Vite rollup plugins.
2. **Upgrade `firebase` to 11.x**: **REJECTED for Phase 2.9**. Firebase 11 contains breaking API changes in modular auth and service worker APIs that could risk regression in staging.
3. **Targeted npm Override (`package.json` `overrides`)**: **SELECTED**.
   - `undici@^6.28.1` is a backward-compatible drop-in replacement that addresses all 15 published advisories while preserving the exact Firebase 10.8.0 API contract.

### Implemented Configuration (`frontend/package.json`):
```json
"overrides": {
  "undici": "^6.28.1"
}
```

---

## 4. Verification & Audit Results (After Mitigation)

Command executed:
```bash
cd frontend
npm audit
```

Output:
```text
found 0 vulnerabilities
```

### Verification Gate Status:
- `npm audit`: **0 vulnerabilities**
- `npm run lint`: **0 errors**
- `npm run test:coverage`: **40/40 tests passing**
- `npm run build`: **Build successful**
- `npm run test:e2e:ui-contract`: **6/6 contract tests passing**

---

## 5. Unresolved Advisories & Justifications

**None.** All vulnerabilities (critical, high, and moderate) have been completely resolved.
