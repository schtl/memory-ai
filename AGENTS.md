# Repository instructions

## Bilingual documentation

- Maintain English and German documentation together in the same change.
- Keep `README.md` and `README.de.md` equivalent in scope and technical meaning.
- Keep `proxy/apache/README.md` and `proxy/apache/README.de.md` equivalent too.
- Update commands, configuration examples, requirements and limitations in both
  languages whenever behavior changes. Do not leave translations for a later commit.
- Keep language navigation links in both versions.
- Code, identifiers, configuration keys and filenames remain English.

## Privacy in documentation and examples

- Never include real user domains, account names, personal email addresses,
  credentials or other identifying deployment details in documentation or examples.
- Use reserved example domains such as `example.org`, synthetic values and neutral
  placeholders such as `YOUR_ACCOUNT`.
- Actual deployment settings belong only in the ignored local `.env` and ignored
  generated configuration. Do not commit these files.

## Validation

- Verify that paired documentation uses equivalent command/configuration blocks
  and that local documentation links resolve.
- Report validation limits accurately; do not claim Docker, provider or production
  Apache checks passed unless they were actually executed.
