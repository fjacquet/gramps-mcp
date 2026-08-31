# Gramps Web API coverage

Generated from `openapi.json`, **Gramps Web API 3.21.1**, by `scripts/gen_api_reference.py`.
Do not edit this page by hand - regenerate it.

This server calls **96 of the 193 operations** the API exposes.
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
| GET | `/api/anniversaries.ics` | - | Return anniversaries in ICS format. |

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
| GET | `/api/citations/` | `GET_CITATIONS` | Get all objects. |
| POST | `/api/citations/` | `POST_CITATIONS` | Post a new object. |
| POST | `/api/citations/query/` | - | Run a structured query. |
| DELETE | `/api/citations/{handle}` | `DELETE_CITATION` | Delete the object. |
| GET | `/api/citations/{handle}` | `GET_CITATION` | Get the object. |
| PUT | `/api/citations/{handle}` | `PUT_CITATION` | Modify an existing object. |
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
| GET | `/api/events/` | `GET_EVENTS` | Get all objects. |
| POST | `/api/events/` | `POST_EVENTS` | Post a new object. |
| POST | `/api/events/query/` | - | Run a structured query. |
| GET | `/api/events/{handle1}/span/{handle2}` | `GET_EVENT_SPAN` | Get the time span between two event dates. |
| DELETE | `/api/events/{handle}` | `DELETE_EVENT` | Delete the object. |
| GET | `/api/events/{handle}` | `GET_EVENT` | Get the object. |
| PUT | `/api/events/{handle}` | `PUT_EVENT` | Modify an existing object. |
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
| GET | `/api/families/` | `GET_FAMILIES` | Get all objects. |
| POST | `/api/families/` | `POST_FAMILIES` | Post a new object. |
| POST | `/api/families/query/` | - | Run a structured query. |
| DELETE | `/api/families/{handle}` | `DELETE_FAMILY` | Delete the object. |
| GET | `/api/families/{handle}` | `GET_FAMILY` | Get the object. |
| PUT | `/api/families/{handle}` | `PUT_FAMILY` | Modify an existing object. |
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
| GET | `/api/media/` | `GET_MEDIA` | Get all objects. |
| POST | `/api/media/` | `POST_MEDIA` | Post a new object. |
| POST | `/api/media/archive/` | - | Create an archive of media files. |
| POST | `/api/media/archive/upload/zip` | - | Upload an archive of media files. |
| GET | `/api/media/archive/{filename}` | - | Download an archive of media files. |
| POST | `/api/media/query/` | - | Run a structured query. |
| DELETE | `/api/media/{handle}` | `DELETE_MEDIA_ITEM` | Delete the object. |
| GET | `/api/media/{handle}` | `GET_MEDIA_ITEM` | Get the object. |
| PUT | `/api/media/{handle}` | `PUT_MEDIA_ITEM` | Modify an existing object. |
| GET | `/api/media/{handle}/face_detection` | - | Get detected face regions. |
| GET | `/api/media/{handle}/file` | `GET_MEDIA_FILE` | Download a file. |
| PUT | `/api/media/{handle}/file` | `PUT_MEDIA_FILE` | Upload a file and update the media object. |
| POST | `/api/media/{handle}/ocr` | - | Execute OCR on a file. |
| POST | `/api/media/{phoenix_handle}/merge/{titanic_handle}` | `MERGE_MEDIA` | Merge two objects. Phoenix survives; titanic is deleted. |

## Metadata

0 of 3 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/metadata/` | - | Get active database and application related metadata information. |
| GET | `/api/metadata/researcher/` | - | Get the researcher information. |
| PUT | `/api/metadata/researcher/` | - | Update the researcher information. |

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
| GET | `/api/notes/` | `GET_NOTES` | Get all objects. |
| POST | `/api/notes/` | `POST_NOTES` | Post a new object. |
| POST | `/api/notes/query/` | - | Run a structured query. |
| DELETE | `/api/notes/{handle}` | `DELETE_NOTE` | Delete the object. |
| GET | `/api/notes/{handle}` | `GET_NOTE` | Get the object. |
| PUT | `/api/notes/{handle}` | `PUT_NOTE` | Modify an existing object. |
| POST | `/api/notes/{phoenix_handle}/merge/{titanic_handle}` | `MERGE_NOTE` | Merge two objects. Phoenix survives; titanic is deleted. |

## OIDC

0 of 6 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/oidc/callback/` | - | Handle OIDC callback and create JWT tokens. |
| GET | `/api/oidc/callback/{provider_id}` | - | Handle OIDC callback and create JWT tokens. |
| GET | `/api/oidc/config/` | - | Get OIDC configuration for frontend. |
| GET | `/api/oidc/login/` | - | Redirect to OIDC provider for authentication. |
| GET | `/api/oidc/logout/` | - | Get OIDC logout URL for the specified provider. |
| POST | `/api/oidc/tokens/` | - | Exchange the code from the login redirect for tokens. |

## People

6 of 7 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/people/` | `GET_PEOPLE` | Get all objects. |
| POST | `/api/people/` | `POST_PEOPLE` | Post a new object. |
| POST | `/api/people/query/` | - | Run a structured query. |
| DELETE | `/api/people/{handle}` | `DELETE_PERSON` | Delete the object. |
| GET | `/api/people/{handle}` | `GET_PERSON` | Get the object. |
| PUT | `/api/people/{handle}` | `PUT_PERSON` | Modify an existing object. |
| POST | `/api/people/{phoenix_handle}/merge/{titanic_handle}` | `MERGE_PERSON` | Merge two people. Phoenix survives; titanic is deleted. |

## Places

6 of 7 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/places/` | `GET_PLACES` | Get all objects. |
| POST | `/api/places/` | `POST_PLACES` | Post a new object. |
| POST | `/api/places/query/` | - | Run a structured query. |
| DELETE | `/api/places/{handle}` | `DELETE_PLACE` | Delete the object. |
| GET | `/api/places/{handle}` | `GET_PLACE` | Get the object. |
| PUT | `/api/places/{handle}` | `PUT_PLACE` | Modify an existing object. |
| POST | `/api/places/{phoenix_handle}/merge/{titanic_handle}` | `MERGE_PLACE` | Merge two objects. Phoenix survives; titanic is deleted. |

## Relations

2 of 2 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/relations/{handle1}/{handle2}` | `GET_RELATIONS` | Get the most direct relationship between two people. |
| GET | `/api/relations/{handle1}/{handle2}/all` | `GET_RELATIONS_ALL` | Get all possible relationships between two people. |

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
| GET | `/api/repositories/` | `GET_REPOSITORIES` | Get all objects. |
| POST | `/api/repositories/` | `POST_REPOSITORIES` | Post a new object. |
| POST | `/api/repositories/query/` | - | Run a structured query. |
| DELETE | `/api/repositories/{handle}` | `DELETE_REPOSITORY` | Delete the object. |
| GET | `/api/repositories/{handle}` | `GET_REPOSITORY` | Get the object. |
| PUT | `/api/repositories/{handle}` | `PUT_REPOSITORY` | Modify an existing object. |
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
| GET | `/api/sources/` | `GET_SOURCES` | Get all objects. |
| POST | `/api/sources/` | `POST_SOURCES` | Post a new object. |
| POST | `/api/sources/query/` | - | Run a structured query. |
| DELETE | `/api/sources/{handle}` | `DELETE_SOURCE` | Delete the object. |
| GET | `/api/sources/{handle}` | `GET_SOURCE` | Get the object. |
| PUT | `/api/sources/{handle}` | `PUT_SOURCE` | Modify an existing object. |
| POST | `/api/sources/{phoenix_handle}/merge/{titanic_handle}` | `MERGE_SOURCE` | Merge two objects. Phoenix survives; titanic is deleted. |

## Tags

5 of 6 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/tags/` | `GET_TAGS` | Get all objects. |
| POST | `/api/tags/` | `POST_TAGS` | Post a new object. |
| POST | `/api/tags/query/` | - | Run a structured query. |
| DELETE | `/api/tags/{handle}` | `DELETE_TAG` | Delete the object. |
| GET | `/api/tags/{handle}` | `GET_TAG` | Get the object. |
| PUT | `/api/tags/{handle}` | `PUT_TAG` | Modify an existing object. |

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

1 of 4 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| POST | `/api/token/` | `AuthManager auth.py:128 (not via ApiCalls)` | Post username and password to fetch a token. |
| GET | `/api/token/create_owner/` | - | Get a token. |
| POST | `/api/token/create_owner/` | - | Get a token. |
| POST | `/api/token/refresh/` | - | Fetch a new token. |

## Transactions

3 of 8 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| POST | `/api/objects/` | - | Post the objects. |
| POST | `/api/objects/delete-by-handle/` | - | Delete the objects. |
| POST | `/api/objects/delete/` | - | Delete the objects. |
| POST | `/api/transactions/` | - | Post the transaction. |
| GET | `/api/transactions/history/` | `GET_TRANSACTIONS_HISTORY` | Return a list of transactions. |
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

4 of 16 used.

| Method | Path | ApiCalls | Summary |
|---|---|---|---|
| GET | `/api/users/` | `GET_USERS` | Get users' details. |
| POST | `/api/users/` | - | Add one or more users. |
| DELETE | `/api/users/-/access-tokens/{scope}/` | - | Revoke persistent token for current user and scope. |
| GET | `/api/users/-/access-tokens/{scope}/` | - | Get persistent token status for current user and scope. |
| POST | `/api/users/-/access-tokens/{scope}/` | - | Create or rotate persistent token for current user and scope. |
| GET | `/api/users/-/email/confirm/` | - | Show email confirmation dialog. |
| GET | `/api/users/-/password/reset/` | - | Reset password form. |
| POST | `/api/users/-/password/reset/` | - | Post new password. |
| DELETE | `/api/users/{user_name}/` | `DELETE_USER` | Delete a user. |
| GET | `/api/users/{user_name}/` | `GET_USER` | Get a user's details. |
| POST | `/api/users/{user_name}/` | `POST_USER` |  |
| PUT | `/api/users/{user_name}/` | - | Update a user's details. |
| POST | `/api/users/{user_name}/create_owner/` | - | Create a user with admin permissions. |
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
