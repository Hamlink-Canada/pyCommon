# Current decisions

The credential model and its versioned migrations belong to `pyCommon`, so all
consumers share one schema contract. Central Auth uses the model for read-only
lookups. Schema changes run through the explicit `rpt-common-migrate` command with
a migration account; the service never runs migrations at startup. Provisioning and
credential lifecycle operations are outside this repository's scope.

Shared entity identities, their primary and AKA call signs, ownership, and
Entity Super Admin assignments also belong in `pyCommon`. Entity type is one of
organization, club, or association. Call signs are globally unique and stored
in uppercase; an entity may have none, but AKA call signs require a primary
call sign. Assigning an owner clears system-maintained status. Returning an
entity to system-maintained status clears its owner; a local admin CLI is
responsible for removing its Entity Super Admin assignments as part of that
operation. Local administration can also transfer Entity ownership. User IDs
are external Keycloak subject strings, not local user rows.

The entity tables are introduced by the additive `0002_shared_entities`
migration. Credential consumers accept both the old credential-only revision
and this new shared-schema revision during coordinated package rollouts.
