# System architecture

Two phases:

- **Build phase** — you drive SpecKit in Copilot Chat (`/speckit.*`),
  Copilot agent mode generates the Watchdog source.
- **Run phase** — you capture telemetry from the sim, the Watchdog
  agent (the source you just generated, now running) reads it, calls
  detection tools and the Copilot LLM, and emits a JSON answer that
  you copy/paste into the leaderboard web form.

```mermaid
flowchart TB
    subgraph BUILD["Build phase — Spec-Driven flow"]
        direction LR
        S1[Student] -->|"/speckit.*"| S2["SpecKit in<br/>Copilot Chat"]
        S2 -->|spec / plan| S3["Copilot agent<br/>writes code"]
        S3 --> S4["Watchdog source"]
    end

    subgraph RUN["Run phase — capture, analyse, submit"]
        SIM[Sim] -->|WebSocket| CAP[capture.py]
        CAP -->|writes| JSONL[(telemetry.jsonl)]
        JSONL -->|load| AGENT

        subgraph AGENT["Watchdog Agent — GitHubCopilotAgent"]
            T1["@tool detect_pattern_1"]
            T2["@tool detect_pattern_2"]
            T3["@tool detect_pattern_3"]
            T4["@tool detect_pattern_4"]
        end

        AGENT <-->|LLM call| API[GitHub Copilot API]
        AGENT -->|answer JSON| SCHEMA[jsonschema validation]
        SCHEMA -->|copy / paste| LB[Leaderboard web form]
    end

    S4 -.->|deployed at runtime| AGENT

    classDef src fill:#a5d8ff,stroke:#4a9eed,color:#0c3a7a
    classDef cmd fill:#fff3bf,stroke:#f59e0b,color:#7c4a03
    classDef code fill:#d0bfff,stroke:#8b5cf6,color:#4c1d95
    classDef proc fill:#b2f2bb,stroke:#22c55e,color:#15803d
    classDef ext fill:#ffd8a8,stroke:#f59e0b,color:#7c4a03
    classDef store fill:#c3fae8,stroke:#06b6d4,color:#0e7490
    classDef out fill:#eebefa,stroke:#ec4899,color:#9d174d

    class S1,API src
    class S2,T1,T2,T3,T4,SCHEMA cmd
    class S3 code
    class S4,CAP proc
    class SIM ext
    class JSONL store
    class LB out

    style S4 stroke-dasharray: 5 5
    style BUILD fill:#e5dbff,stroke:#8b5cf6,stroke-width:1px
    style RUN fill:#dbe4ff,stroke:#4a9eed,stroke-width:1px
    style AGENT fill:#ede5ff,stroke:#8b5cf6,stroke-width:2px
```

## Reading the diagram

| Element | What it is |
|---|---|
| **Sim** | Black-box dependency (`sim` package, pinned to `v0.2.0`). Emits a merged WebSocket stream of nested per-scenario sub-objects. |
| **capture.py** | Reconnect-forever WebSocket client. Writes one JSONL frame per line. |
| **telemetry.jsonl** | Your captured frames — what every detector reads. |
| **Watchdog Agent** | A single `GitHubCopilotAgent` from `agent-framework-github-copilot`, with 4 `@tool`-decorated detector functions and a permission handler that approves all tool calls. |
| **GitHub Copilot API** | The LLM that decides which tools to call and assembles the final JSON. Auth via `make login`. |
| **jsonschema validation** | Last-line check against `specs/submission_schema.json` before you submit. |
| **Leaderboard web form** | The leaderboard collects `name` and `department` separately; you paste only the `answer` JSON. |
