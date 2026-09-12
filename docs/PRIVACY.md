# Privacy and data handling

Product Excellence runs browser tests locally, but an AI-enabled test is not
fully offline. Use test accounts and avoid confidential pages unless you have
permission to send their contents to the configured services.

| Data | Where it goes |
| --- | --- |
| Website requests and sign-in | The target website; through your proxy if configured |
| Selected page observations, goals and screenshots | The selected AI provider through its signed-in CLI, when AI is enabled |
| Local records and evidence | `data/` by default, or your configured `PEX_DATA` directory |
| Mission passwords and proxy credentials | Local files under `data/secrets/`; not normal mission exports |
| Saved browser sessions | Local persona files, containing cookies and browser storage |
| Team server credentials | Local `data/hub.json`, with restricted file permissions |
| Shared missions, runs and evidence | Your connected team server; published automatically when configured |
| Playwright traces | Local artifacts; excluded from team-server publication |

Provider subscription quotas and the provider’s own data handling settings apply.
**No AI** audits do not send evidence to an AI worker, but still contact the website.
The project does not include a hosted account or a shared provider subscription.

## Redaction has limits

The engine fills stored mission passwords without putting them in the AI action.
It removes exact reflected password text from structured observations and common
text captures, and masks selected password, email, phone and one-time-code inputs
in screenshots. This does not recognize every encoded secret or every kind of
personal information. Page text, URLs, images, video and traces may contain
credentials, signed-in content or personal data. Video is not comprehensively masked.

Raw evidence is intentionally retained for debugging. Shared workspace members
can read its shared evidence; a shared login does not identify individual people.
Review reports and media before posting them to GitHub, sending them to another
person or publishing a run. Never upload a complete local project folder: it may
include ignored runtime files.

## Retention and removal

Evidence and local sessions remain until you remove them. Stop the app before
removing private files or making a backup. Deleting a local copy does not remove
copies already published to a team server, copied into backups, exported, or sent
to an AI provider. Coordinate removal with the relevant server administrator and
provider controls. Restrict access to backups and use device encryption.

For source publication, use the [public release guide](PUBLIC_RELEASE.md).
