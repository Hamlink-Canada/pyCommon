# Current decisions

The credential model and its versioned migrations belong to `pyCommon`, so all
consumers share one schema contract. Central Auth uses the model for read-only
lookups. Schema changes run through the explicit `rpt-common-migrate` command with
a migration account; the service never runs migrations at startup. Provisioning and
credential lifecycle operations are outside this repository's scope.
