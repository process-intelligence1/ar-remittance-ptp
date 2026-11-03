# Snapshot safety check - 2026-11-03

Result: **PASSED** (0 problem(s))

## What was exported
- 504 work items from 234 e-mails ({'history': 187, 'sample': 47, 'upload': 0}); 0 other e-mail(s) in the database were NOT exported.
- 189 attachments in the manifest: 188 are plain sample files (copied from data/samples when the site is built), 1 unpacked from ZIP files are exported.
- 2846 audit rows, 58 promises, business date 2026-10-28.

## Checks
- E-mail addresses found in the export: 85; not in the sample files / SAP master data / read attachment texts / demo users: **0** (must be 0).
- Searched every exported JSON file for: the demo mailbox, an Azure host name, a bearer token / JWT, a private key, a client secret / token field, a signed download link, a database URL.
- Every work item belongs to a live / history sample e-mail (source sample / upload / history): yes.
- Every exported attachment file belongs to a live / history sample: yes.
- The gitleaks workflow ('Secret scan') must also be green on the commit that contains snapshot/.

## Size
- snapshot/data (JSON): 12.3 MB; snapshot/files: 0.0 MB
- sample files referenced by the manifest (copied at site build): 40.8 MB
- PDF page images (118 pages, rendered at site build, estimate 70 KB each): 8.1 MB
- **Estimated site size: 61.2 MB** (limit 300 MB). The measured size of the assembled site is added by scripts/build_site_files.py.
