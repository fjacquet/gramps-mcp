# User guide

This guide is for someone who already has the server running and wants to get
good results out of it through an AI assistant.
[Installation](../getting-started/installation.md),
[configuration](../getting-started/configuration.md) and the full
[tool inventory](../reference/tools.md) live elsewhere; nothing here repeats
them.

Everything below is phrased as tool calls because that is what the assistant
issues on your behalf. You will normally type ordinary sentences ("find the
Vilpellet marriage in 1885 and source it from this scan"); knowing the tool
names is what lets you tell whether the assistant did the right thing, and
correct it when it did not.

## Two resources to read first

The server ships two MCP resources, and a session that has not read them tends
to guess:

- `gramps://usage-guide` - the sourcing workflow the tools expect. Ask the
  assistant to read it before any data entry session.
- `gql://documentation` - the Gramps Query Language syntax and the full
  property list. Required before writing anything but the simplest `find_type`
  filter.

Both are also useful to you directly. If a search keeps returning nothing, the
property list in the GQL resource is usually the reason.

## The rest of the guide

The pages below follow the order of a normal session: find the record, read it,
write to it, then check what you did.

- **[Searching and reading records](searching.md)** - `find_anything` and
  `find_type` for locating people and families, `get_type`, `get_timeline` and
  `get_facts` for reading one in depth.
- **[Recording a sourced fact](recording.md)** - the
  repository-source-citation-event chain, the composite tool that collapses it,
  dates, places, and attaching scans.
- **[Relationships, timelines and recent changes](exploring.md)** - how two
  people connect, whether someone is probably living, and auditing what a
  session wrote.
- **[Managing accounts](administration.md)** - creating Gramps Web accounts in
  batches with `manage_users`.
- **[Things that will surprise you](gotchas.md)** - the behaviours that catch
  people out, starting with the fact that nothing can be removed from a list.
