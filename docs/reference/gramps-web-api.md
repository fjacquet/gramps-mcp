# Gramps Web API coverage

Generated from `openapi.json`, **Gramps Web API 3.26.0**, by `scripts/gen_api_reference.py`.
Do not edit this page by hand - regenerate it.

This server calls **96 of the 217 operations** the API exposes.
A row with an `ApiCalls` member is reachable from an MCP tool; a row
without one is a capability this server does not use today.

Paths are shown as the spec writes them. The REST base is
`${GRAMPS_API_URL%/}/api` - `GRAMPS_API_URL` itself carries no `/api`
suffix, and calling it without one returns the web app's HTML page with
HTTP 200 rather than an error.

## Anniversaries

0 of 1 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/anniversaries.ics` | - | Return exact anniversaries recurring from last year onward. |

## Backups

0 of 6 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/backups/` | - | List the tree's stored backups, newest first. |
| POST | `/api/backups/` | - | Create a stored backup of the tree. |
| POST | `/api/backups/restore` | - | Restore the selected parts of the tree from an uploaded backup archive. |
| DELETE | `/api/backups/{backup_id}` | - | Delete a stored backup. |
| GET | `/api/backups/{backup_id}` | - | Download a stored backup archive. |
| POST | `/api/backups/{backup_id}/restore` | - | Restore the selected parts of the tree from a stored backup. |

## Bookmarks

0 of 4 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/bookmarks/` | - | Get the list of bookmark types. |
| GET | `/api/bookmarks/{namespace}` | - | Get list of bookmarks by namespace. |
| DELETE | `/api/bookmarks/{namespace}/{handle}` | - |  |
| PUT | `/api/bookmarks/{namespace}/{handle}` | - | Create a bookmark. |

## Chat

0 of 1 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| POST | `/api/chat/` | - | Create a chat response. |

## Citations

6 of 7 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/citations/` | `GET_CITATIONS` | List Gramps citations with filters |
| POST | `/api/citations/` | `POST_CITATIONS` | Create a Gramps Citation record |
| POST | `/api/citations/query/` | - | Run a structured query. |
| DELETE | `/api/citations/{handle}` | `DELETE_CITATION` | Delete a Gramps Citation record |
| GET | `/api/citations/{handle}` | `GET_CITATION` | Get a Gramps Citation record |
| PUT | `/api/citations/{handle}` | `PUT_CITATION` | Update a Gramps Citation record |
| POST | `/api/citations/{phoenix_handle}/merge/{titanic_handle}` | `MERGE_CITATION` | Merge two objects. Phoenix survives; titanic is deleted. |

## Config

0 of 4 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/config/` | - | Get all config settings. |
| DELETE | `/api/config/{key}/` | - | Delete a config setting. |
| GET | `/api/config/{key}/` | - | Get a config setting. |
| PUT | `/api/config/{key}/` | - | Update a config setting. |

## DNA

2 of 3 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| POST | `/api/parsers/dna-match` | `POST_PARSERS_DNA_MATCH` | Parse DNA match string. |
| GET | `/api/people/{handle}/dna/matches` | `GET_PERSON_DNA_MATCHES` | Get the DNA match data. |
| GET | `/api/people/{handle}/ydna` | - | Get Y-DNA data. |

## Events

7 of 8 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/events/` | `GET_EVENTS` | List Gramps events with filters |
| POST | `/api/events/` | `POST_EVENTS` | Create a Gramps Event record |
| POST | `/api/events/query/` | - | Run a structured query. |
| GET | `/api/events/{handle1}/span/{handle2}` | `GET_EVENT_SPAN` | Get the time span between two event dates. |
| DELETE | `/api/events/{handle}` | `DELETE_EVENT` | Delete a Gramps Event record |
| GET | `/api/events/{handle}` | `GET_EVENT` | Get a Gramps Event record |
| PUT | `/api/events/{handle}` | `PUT_EVENT` | Update a Gramps Event record |
| POST | `/api/events/{phoenix_handle}/merge/{titanic_handle}` | `MERGE_EVENT` | Merge two objects. Phoenix survives; titanic is deleted. |

## Exporters

0 of 5 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/exporters/` | - | Get all available exporter attributes. |
| GET | `/api/exporters/{extension}` | - | Get specific report attributes. |
| GET | `/api/exporters/{extension}/file` | - | Get export file. |
| POST | `/api/exporters/{extension}/file` | - | Create the export. |
| GET | `/api/exporters/{extension}/file/processed/{filename}` | - | Get the processed file. |

## Facts

1 of 1 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/facts/` | `GET_FACTS` | Get statistics from records. |

## Families

6 of 7 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/families/` | `GET_FAMILIES` | List Gramps families with filters |
| POST | `/api/families/` | `POST_FAMILIES` | Create a Gramps Family record |
| POST | `/api/families/query/` | - | Run a structured query. |
| DELETE | `/api/families/{handle}` | `DELETE_FAMILY` | Delete a Gramps Family record |
| GET | `/api/families/{handle}` | `GET_FAMILY` | Get a Gramps Family record |
| PUT | `/api/families/{handle}` | `PUT_FAMILY` | Update a Gramps Family record |
| POST | `/api/families/{phoenix_handle}/merge/{titanic_handle}` | `MERGE_FAMILY` | Merge two families. Phoenix survives; titanic is deleted. |

## Filters

0 of 6 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/filters/` | - | Get available custom filters and rules. |
| GET | `/api/filters/{namespace}` | - | Get available custom filters and rules. |
| POST | `/api/filters/{namespace}` | - | Create a custom filter. |
| PUT | `/api/filters/{namespace}` | - | Update a custom filter. |
| DELETE | `/api/filters/{namespace}/{name}` | - | Delete a custom filter. |
| GET | `/api/filters/{namespace}/{name}` | - | Get a custom filter. |

## Holidays

2 of 2 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/holidays/` | `GET_HOLIDAYS` | Get list of countries that have holiday calendars. |
| GET | `/api/holidays/{country}/{year}/{month}/{day}` | `GET_HOLIDAYS_DATE` | If the given day is a holiday return the name or names. |

## Importers

0 of 4 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/importers/` | - | Get all available importer attributes. |
| GET | `/api/importers/{extension}` | - | Get specific report attributes. |
| POST | `/api/importers/{extension}/file` | - | Import file. |
| POST | `/api/importers/{extension}/file/restore` | - | Reset the tree to match an uploaded backup, replacing its contents. |

## Living

2 of 2 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/living/{handle}` | `GET_LIVING` | Determine if person alive. |
| GET | `/api/living/{handle}/dates` | `GET_LIVING_DATES` | Determine estimated birth and death dates. |

## Media

8 of 14 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/media/` | `GET_MEDIA` | List Gramps media objects with filters |
| POST | `/api/media/` | `POST_MEDIA` | Create a Gramps Media record |
| POST | `/api/media/archive/` | - | Create an archive of media files. |
| POST | `/api/media/archive/upload/zip` | - | Upload an archive of media files. |
| GET | `/api/media/archive/{filename}` | - | Download an archive of media files. |
| POST | `/api/media/query/` | - | Run a structured query. |
| DELETE | `/api/media/{handle}` | `DELETE_MEDIA_ITEM` | Delete a Gramps Media record |
| GET | `/api/media/{handle}` | `GET_MEDIA_ITEM` | Get a Gramps Media record |
| PUT | `/api/media/{handle}` | `PUT_MEDIA_ITEM` | Update a Gramps Media record |
| GET | `/api/media/{handle}/face_detection` | - | Get detected face regions. |
| GET | `/api/media/{handle}/file` | `GET_MEDIA_FILE` | Download a file. |
| PUT | `/api/media/{handle}/file` | `PUT_MEDIA_FILE` | Upload a file and update the media object. |
| POST | `/api/media/{handle}/ocr` | - | Execute OCR on a file. |
| POST | `/api/media/{phoenix_handle}/merge/{titanic_handle}` | `MERGE_MEDIA` | Merge two objects. Phoenix survives; titanic is deleted. |

## Metadata

0 of 4 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/metadata/` | - | Get active database and application related metadata information. |
| GET | `/api/metadata/researcher/` | - | Get the researcher information. |
| PUT | `/api/metadata/researcher/` | - | Update the researcher information. |
| GET | `/api/metadata/server/` | - | Get application related metadata that does not depend on a tree. |

## Name Formats

0 of 1 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/name-formats/` | - | Get list of name formats. |

## Name Groups

0 of 6 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/name-groups/` | - | Get list of name group mappings. |
| POST | `/api/name-groups/` | - | Set a name group mapping. |
| GET | `/api/name-groups/{surname}` | - | Get list of name group mappings. |
| POST | `/api/name-groups/{surname}` | - | Set a name group mapping. |
| GET | `/api/name-groups/{surname}/{group}` | - | Get list of name group mappings. |
| POST | `/api/name-groups/{surname}/{group}` | - | Set a name group mapping. |

## Notes

6 of 7 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/notes/` | `GET_NOTES` | List Gramps notes with filters |
| POST | `/api/notes/` | `POST_NOTES` | Create a Gramps Note record |
| POST | `/api/notes/query/` | - | Run a structured query. |
| DELETE | `/api/notes/{handle}` | `DELETE_NOTE` | Delete a Gramps Note record |
| GET | `/api/notes/{handle}` | `GET_NOTE` | Get a Gramps Note record |
| PUT | `/api/notes/{handle}` | `PUT_NOTE` | Update a Gramps Note record |
| POST | `/api/notes/{phoenix_handle}/merge/{titanic_handle}` | `MERGE_NOTE` | Merge two objects. Phoenix survives; titanic is deleted. |

## OIDC

0 of 8 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/oidc/callback/` | - | Handle OIDC callback and create JWT tokens. |
| GET | `/api/oidc/callback/{provider_id}` | - | Handle OIDC callback and create JWT tokens. |
| GET | `/api/oidc/config/` | - | Get OIDC configuration for frontend. |
| POST | `/api/oidc/link/` | - | Return a ticket for linking a provider identity to the current user. |
| POST | `/api/oidc/link/complete/` | - | Link the identity from the callback to the current user. |
| GET | `/api/oidc/login/` | - | Redirect to OIDC provider for authentication. |
| GET | `/api/oidc/logout/` | - | Get OIDC logout URL for the specified provider. |
| POST | `/api/oidc/tokens/` | - | Exchange the code from the login redirect for tokens. |

## People

6 of 7 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/people/` | `GET_PEOPLE` | List Gramps people with filters |
| POST | `/api/people/` | `POST_PEOPLE` | Create a Gramps Person record |
| POST | `/api/people/query/` | - | Run a structured query. |
| DELETE | `/api/people/{handle}` | `DELETE_PERSON` | Delete a Gramps Person record |
| GET | `/api/people/{handle}` | `GET_PERSON` | Get a Gramps Person record |
| PUT | `/api/people/{handle}` | `PUT_PERSON` | Update a Gramps Person record |
| POST | `/api/people/{phoenix_handle}/merge/{titanic_handle}` | `MERGE_PERSON` | Merge two people. Phoenix survives; titanic is deleted. |

## Places

6 of 8 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/places/` | `GET_PLACES` | List Gramps places with filters |
| POST | `/api/places/` | `POST_PLACES` | Create a Gramps Place record |
| GET | `/api/places/coordinates/` | - | Get the name and coordinates of all places, in no particular order. |
| POST | `/api/places/query/` | - | Run a structured query. |
| DELETE | `/api/places/{handle}` | `DELETE_PLACE` | Delete a Gramps Place record |
| GET | `/api/places/{handle}` | `GET_PLACE` | Get a Gramps Place record |
| PUT | `/api/places/{handle}` | `PUT_PLACE` | Update a Gramps Place record |
| POST | `/api/places/{phoenix_handle}/merge/{titanic_handle}` | `MERGE_PLACE` | Merge two objects. Phoenix survives; titanic is deleted. |

## Relations

2 of 3 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/relations/{handle1}/{handle2}` | `GET_RELATIONS` | Get the most direct relationship between two people. |
| GET | `/api/relations/{handle1}/{handle2}/all` | `GET_RELATIONS_ALL` | Get all possible relationships between two people. |
| GET | `/api/relations/{handle1}/{handle2}/paths` | - | Get the chains of family links between two people, shortest first. |

## Reports

5 of 5 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/reports/` | `GET_REPORTS` | Get all available report attributes. |
| GET | `/api/reports/{report_id}` | `GET_REPORT` | Get specific report attributes. |
| GET | `/api/reports/{report_id}/file` | `GET_REPORT_FILE` | Get specific report attributes. |
| POST | `/api/reports/{report_id}/file` | `POST_REPORT_FILE` | Create the report. |
| GET | `/api/reports/{report_id}/file/processed/{filename}` | `GET_REPORT_PROCESSED` | Get the processed file. |

## Repositories

6 of 7 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/repositories/` | `GET_REPOSITORIES` | List Gramps repositories with filters |
| POST | `/api/repositories/` | `POST_REPOSITORIES` | Create a Gramps Repository record |
| POST | `/api/repositories/query/` | - | Run a structured query. |
| DELETE | `/api/repositories/{handle}` | `DELETE_REPOSITORY` | Delete a Gramps Repository record |
| GET | `/api/repositories/{handle}` | `GET_REPOSITORY` | Get a Gramps Repository record |
| PUT | `/api/repositories/{handle}` | `PUT_REPOSITORY` | Update a Gramps Repository record |
| POST | `/api/repositories/{phoenix_handle}/merge/{titanic_handle}` | `MERGE_REPOSITORY` | Merge two objects. Phoenix survives; titanic is deleted. |

## Search

1 of 2 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/search/` | `GET_SEARCH` | Get search result. |
| POST | `/api/search/index/` | - | Trigger a reindex. |

## Sources

6 of 7 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/sources/` | `GET_SOURCES` | List Gramps sources with filters |
| POST | `/api/sources/` | `POST_SOURCES` | Create a Gramps Source record |
| POST | `/api/sources/query/` | - | Run a structured query. |
| DELETE | `/api/sources/{handle}` | `DELETE_SOURCE` | Delete a Gramps Source record |
| GET | `/api/sources/{handle}` | `GET_SOURCE` | Get a Gramps Source record |
| PUT | `/api/sources/{handle}` | `PUT_SOURCE` | Update a Gramps Source record |
| POST | `/api/sources/{phoenix_handle}/merge/{titanic_handle}` | `MERGE_SOURCE` | Merge two objects. Phoenix survives; titanic is deleted. |

## Tags

5 of 6 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/tags/` | `GET_TAGS` | List Gramps tags with filters |
| POST | `/api/tags/` | `POST_TAGS` | Create a Gramps Tag record |
| POST | `/api/tags/query/` | - | Run a structured query. |
| DELETE | `/api/tags/{handle}` | `DELETE_TAG` | Delete a Gramps Tag record |
| GET | `/api/tags/{handle}` | `GET_TAG` | Get a Gramps Tag record |
| PUT | `/api/tags/{handle}` | `PUT_TAG` | Update a Gramps Tag record |

## Tasks

1 of 2 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/tasks/` | - | List tasks for the current tree. |
| GET | `/api/tasks/{task_id}` | `GET_TASK_STATUS` | Get info about a task. |

## Timeline

4 of 4 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/families/{handle}/timeline` | `GET_FAMILY_TIMELINE` | Get list of events in timeline for a family. |
| GET | `/api/people/{handle}/timeline` | `GET_PERSON_TIMELINE` | Get list of events in timeline for a person. |
| GET | `/api/timelines/families/` | `GET_TIMELINES_FAMILIES` | Get consolidated list of events in timeline for a list of families. |
| GET | `/api/timelines/people/` | `GET_TIMELINES_PEOPLE` | Get consolidated list of events in timeline for a list of people. |

## Token

1 of 5 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| POST | `/api/token/` | `AuthManager auth.py:128 (not via ApiCalls)` | Post username and password to fetch a token. |
| GET | `/api/token/create_owner/` | - | Get a token. |
| POST | `/api/token/create_owner/` | - | Get a token. |
| POST | `/api/token/refresh/` | - | Fetch a new token. |
| POST | `/api/token/sync/` | - | Exchange a persistent sync token for a short-lived access token. |

## Transactions

3 of 10 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| POST | `/api/objects/` | - | Post the objects. |
| POST | `/api/objects/delete-by-handle/` | - | Delete the objects. |
| POST | `/api/objects/delete/` | - | Delete the objects. |
| POST | `/api/objects/edit-by-handle/` | - | Edit the objects. |
| POST | `/api/transactions/` | - | Replay a raw database transaction. |
| GET | `/api/transactions/history/` | `GET_TRANSACTIONS_HISTORY` | Return a list of transactions. |
| GET | `/api/transactions/history/objects/{obj_class}/{obj_handle}` | - | Return the change history of a single object as a flat list of changes. |
| GET | `/api/transactions/history/{transaction_id}` | `GET_TRANSACTION_HISTORY` | Return a single transaction. |
| GET | `/api/transactions/history/{transaction_id}/undo` | - | Check if a transaction can be undone without conflicts. |
| POST | `/api/transactions/history/{transaction_id}/undo` | `POST_TRANSACTION_UNDO` | Undo a transaction using background processing. |

## Translations

0 of 3 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/translations/` | - | Get available translations. |
| GET | `/api/translations/{language}` | - | Get translation. |
| POST | `/api/translations/{language}` | - | Get translation for posted strings. |

## Trees

2 of 11 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/trees/` | `GET_TREES` | Get info about all trees. |
| POST | `/api/trees/` | - | Create a new tree. |
| GET | `/api/trees/{tree_id}` | `GET_TREE` | Get info about a tree. |
| PUT | `/api/trees/{tree_id}` | - | Modify a tree. |
| GET | `/api/trees/{tree_id}/config` | - | Get the per-tree configuration blob. |
| PUT | `/api/trees/{tree_id}/config` | - | Replace the per-tree configuration blob. |
| POST | `/api/trees/{tree_id}/disable` | - | Disable a tree. |
| POST | `/api/trees/{tree_id}/enable` | - | Disable a tree. |
| POST | `/api/trees/{tree_id}/migrate` | - | Upgrade the schema of a Gramps database (tree). |
| POST | `/api/trees/{tree_id}/repair` | - | Check & repair a Gramps database (tree). |
| POST | `/api/trees/{tree_id}/verify` | - | Run genealogical data verification checks against the database. |

## Types

4 of 6 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/types/` | `GET_TYPES` | Return list of values for the custom type. |
| GET | `/api/types/custom/` | - | Return a list of available custom types. |
| GET | `/api/types/custom/{datatype}` | - | Return list of values for the custom type. |
| GET | `/api/types/default/` | `GET_TYPES_DEFAULT` | Return a list of available default types. |
| GET | `/api/types/default/{datatype}` | `GET_TYPES_DEFAULT_DATATYPE` | Return a list of values for a default type. |
| GET | `/api/types/default/{datatype}/map` | `GET_TYPES_DEFAULT_MAP` | Return the map for a default type. |

## Users

4 of 26 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/register/config/` | - | Get whether new users can register. |
| GET | `/api/users/` | `GET_USERS` | Get users' details. |
| POST | `/api/users/` | - | Add one or more users. |
| DELETE | `/api/users/-/access-tokens/{scope}/` | - | Revoke persistent token for current user and scope. |
| GET | `/api/users/-/access-tokens/{scope}/` | - | Get persistent token status for current user and scope. |
| POST | `/api/users/-/access-tokens/{scope}/` | - | Create or rotate persistent token for current user and scope. |
| GET | `/api/users/-/access-tokens/{scope}/tokens/` | - | List the current user's tokens for the scope, oldest first. |
| POST | `/api/users/-/access-tokens/{scope}/tokens/` | - | Create a new labelled token for the current user and scope. |
| DELETE | `/api/users/-/access-tokens/{scope}/tokens/{token_id}/` | - | Revoke one of the current user's tokens for the scope. |
| GET | `/api/users/-/email/confirm/` | - | Show email confirmation dialog. |
| GET | `/api/users/-/oidc-accounts/` | - | List the current user's OIDC accounts. |
| DELETE | `/api/users/-/oidc-accounts/{account_id}/` | - | Unlink one of the current user's OIDC accounts. |
| GET | `/api/users/-/password/reset/` | - | Reset password form. |
| POST | `/api/users/-/password/reset/` | - | Post new password. |
| DELETE | `/api/users/-/push-subscriptions/` | - | Delete the current browser's Web Push subscription. |
| GET | `/api/users/-/push-subscriptions/` | - | Get the VAPID public key without exposing subscription endpoints. |
| POST | `/api/users/-/push-subscriptions/` | - | Create or update the current browser's Web Push subscription. |
| DELETE | `/api/users/{user_name}/` | `DELETE_USER` | Delete a user. |
| GET | `/api/users/{user_name}/` | `GET_USER` | Get a user's details. |
| POST | `/api/users/{user_name}/` | `POST_USER` |  |
| PUT | `/api/users/{user_name}/` | - | Update a user's details. |
| POST | `/api/users/{user_name}/create_owner/` | - | Create a user with admin permissions. |
| POST | `/api/users/{user_name}/merge/` | - | Merge another user into this one and delete the other user. |
| POST | `/api/users/{user_name}/password/change` | - | Post new password. |
| POST | `/api/users/{user_name}/password/reset/trigger/` | - | Post username to initiate the password reset. |
| POST | `/api/users/{user_name}/register/` | - | Register a new user. |

## api

0 of 4 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/media/{handle}/cropped/{x1}/{y1}/{x2}/{y2}` | - | Get the thumbnail of a cropped file. |
| GET | `/api/media/{handle}/cropped/{x1}/{y1}/{x2}/{y2}/thumbnail/{size}` | - | Get the thumbnail of a cropped file. |
| GET | `/api/media/{handle}/thumbnail/{size}` | - | Get a file's thumbnail. |
| GET | `/api/media/{handle}/tile/{z}/{x}/{y}` | - | Get a map tile for a georeferenced media image. |
