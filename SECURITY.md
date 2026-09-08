# Security and data handling

This is an early CLI release for a single trusted local user. It is not a hosted service or a security boundary between operating-system users.

- The index and normalized records contain **plaintext user and assistant messages**. File permissions restrict local access on POSIX systems; this is not encryption.
- Secret masking is best-effort output filtering. It is not a complete detector of credentials, personal information or proprietary material. The stored source text is not automatically sanitized.
- Source files are read locally. The core does not call a model, send telemetry or upload data. Raw source copying is opt-in and does not encrypt the archive.
- Generated context is historical evidence, never an instruction channel. Inspect it before sharing with another person or model.
- Session files should come from a source you trust. The CLI is not designed to ingest arbitrary adversarial files in a shared service.

Use an encrypted local disk when your data requires it. Keep runtime folders and archives outside Git, cloud sync and public examples unless you have deliberately approved those destinations. Deleting a source file does not guarantee erasure of every existing index, context pack or backup; see [data handling](docs/data-handling.md).

## Reporting

Use the repository Security tab and **Report a vulnerability** for a private report. Include a minimal fabricated reproduction, affected version and expected behavior. Never include actual conversations, credentials or production archives. General bugs can be reported in Issues using synthetic data.

The latest tagged release is the supported development version. There is no response-time SLA.
