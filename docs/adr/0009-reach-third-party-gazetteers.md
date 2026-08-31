# 9. Reach third-party gazetteers for place resolution

Date: 2026-08-30

## Status

Accepted

## Context

Through v1.10.1 this server made outbound requests to exactly one host: the
user's own Gramps Web instance, named by `GRAMPS_API_URL`. A deployment could
be firewalled to that single destination and everything worked. That property
was never written down as a requirement, but it was true, and people who
deploy servers rely on properties like it whether or not anyone promised them.

`geocode_place` breaks it. Resolving a free-text place name - "Nidau", "Le
Rocher", "Saint-Martin-d'Auxigny" - against an authoritative gazetteer means
asking someone who maintains one. This project's tree is largely French and
Swiss, and the national services for both are open, free and far more accurate
for their own territory than any global service:

- `geo.api.gouv.fr` - the French government's commune API.
- `api3.geo.admin.ch` - the Swiss federal geoportal.
- `query.wikidata.org` - SPARQL, for QIDs and for communes that have merged or
  been renamed.
- `nominatim.openstreetmap.org` - the worldwide fallback, for everywhere else.

The alternative was to vendor a gazetteer: ship the commune lists inside the
image and resolve offline. That keeps the single-destination property, and it
was rejected because the data goes stale in a way that is invisible at the
point of use. French communes merge every year; a place that resolves to a
commune abolished in 2019 produces a confident, wrong answer, and nothing in
the output would show the data was three years old.

## Decision

Call the four services above from `geocode_place`, and confine the dependency
to that tool.

Nominatim's usage policy - one request per second, no burst - is encoded in
`src/gramps_mcp/genealogy/rate_limit.py` and applied to every call. It is
enforced in code rather than left to a comment because it is a term of the
ODbL licence the data is published under, not a performance setting.

`find_duplicates` and `audit_quality` make no outbound calls at all. They
continue to work, completely, when every gazetteer is unreachable.

## Consequences

**A container running this server now needs egress to four hosts it did not
need before.** A deployment locked to the Gramps Web host will see
`geocode_place` fail while every other tool works. That is the correct failure
shape, but it will read as "the server is broken" to anyone who does not know
which tool reaches where, so it is documented in
[Security](../operations/security.md) and in the troubleshooting page rather
than only here.

**Place names leave the user's network.** A genealogy tree is personal data,
and a place name queried against Nominatim is a place name disclosed to the
OpenStreetMap Foundation. No name, date or relationship is sent - the query
carries a place string and nothing else - but the disclosure is real and
belongs on the record.

**The rate limit is not a tuning knob.** Raising it past one request per
second breaches the ODbL terms. Anyone who finds place resolution slow and
reaches for that constant is choosing to breach a licence, and should know it.

**Resolution quality now depends on someone else's uptime and someone else's
data.** A gazetteer that is down is distinguishable from a place that does not
exist only if the tool says which happened - so it must, and the failure paths
are separated for that reason.
