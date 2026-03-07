
```aiignore
ogar/
  pyproject.toml
  README.md
  Makefile
  .env.example

  src/
    ogar/
      __init__.py

      config/
        settings.py            # Pydantic Settings (env-driven)
        logging.py             # log config (optional)

      domain/
        models/                # "business" types (Pydantic) e.g. Plan, Step, ToolEnvelope
        policies/              # gating policy, budgets policy (pure functions)
        services/              # orchestration-facing services (pure logic, no IO)

      ports/                   # interfaces (your "clean boundaries")
        checkpoint_store.py
        event_sink.py
        artifact_store.py
        tool_registry.py
        tool.py
        clock.py               # example of time provider for determinism
        llm.py                 # model interface (optional)
        outbox.py              # notifications/messages (optional)

      adapters/                # implementations (IO lives here)
        persistence/
          postgres/            # or sqlite; keep pluggable
            checkpoint_store.py
            event_store.py
            migrations/        # alembic/sql migrations (if postgres)
          sqlite/
            checkpoint_store.py
            event_store.py
        tools/
          aws/
            s3_client.py       # low-level wrapper ("framework component")
            s3_sink.py         # higher-level sink ("business adapter")
          memgraph/
            client.py
            music_graph_repo.py
        llm/
          openai_client.py
          anthropic_client.py
        observability/
          jsonl_sink.py
          otel_stub.py         # optional
        outbox/
          slack.py             # optional, future

      runtime/
        graph/                 # LangGraph definitions
          build_graph.py
          nodes/
            intake.py
            plan.py
            tool_select.py
            execute_tools.py
            verify.py
            decide.py
            finalize.py
        planner/               # context compiler implementation
          planner.py
          briefing.py
        sidecars/              # spec-driven sidecars
          events.py            # event vocabulary + emit helpers
          tracer.py            # spans, trace context
          metrics.py
          errors.py            # taxonomy
          error_policy.py      # mapping error->action
          budgets.py
          report.py            # run report generator
        engine.py              # "run one graph" entrypoint
        replay.py              # replay tools/events (optional)

      api/
        app.py                 # FastAPI app assembly (transport only)
        routes/
          runs.py              # start/resume/status/report
          eval.py              # run eval suites
        schemas/               # request/response DTOs (transport models)
        deps.py                # dependency wiring (ports -> adapters)
        middleware.py          # request-id, tracing propagation

      cli/
        main.py                # `ogar` CLI entrypoint
        commands/
          run.py
          serve.py
          eval.py

  tests/
    unit/
      domain/
      runtime/
      sidecars/
      ports/
    integration/
      postgres/
      graph_runs/
    scenarios/
      cases/                   # your ≥30 scenarios
      runner_test.py

  eval/
    scenarios.yaml             # optional declarative scenarios
    reports/                   # generated outputs (gitignored)

  deploy/
    k8s/
      base/
        deployment.yaml
        service.yaml
        configmap.yaml
      overlays/
        dev/
        prod/
      helm/                    # optional later

  docker/
    Dockerfile                 # universal image
    entrypoint.sh              # optional

  scripts/
    dev_db.sh                  # starts local Postgres without compose
```