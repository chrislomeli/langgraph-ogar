# 1) Core node labels

Use a small set of labels + a few discriminators.

### :Project

Properties:
id (string, unique)
name
status (active|archived)
created_at, updated_at

### :WorkItem

This is your “task / sub-milestone / milestone / research” unification.
Properties:

id (string, unique)
project_id (string) (denormalized for fast filtering)
title
kind (milestone|task|research|decision|chore)
state (proposed|planned|active|blocked|done|canceled)
priority (int, optional)
due_at (datetime, optional)
estimate_minutes (int, optional)
acceptance (string/json-ish, optional)
created_at, updated_at

### :Outcome (optional but recommended early)

Represents “done means verified outcome”, not just closed tickets.
Properties:

id (string, unique)
project_id
title
criteria (string/json-ish)
state (pending|verified|failed|waived)
created_at, updated_at

### :Artifact

Properties:

id (string, unique)
kind (doc|repo|file|url|pr|build|design)
ref (string) (URL/path/repo ref)
meta (string/json-ish, optional)
created_at

### :Note

Properties:

id (string, unique)
body
tags (list of strings, optional)
created_at

### :Actor

For humans and agents.
Properties:

id (string, unique)
kind (human|agent)
name

### :Event (strongly recommended)

Append-only “what happened”.
Properties:

id (string, unique)
ts (datetime)
actor_id
verb (string)
target_id (string)
payload (string/json-ish)

# 2) Core relationship types

These are the minimal set that unlock your views:

(:Project)-[:HAS_ROOT]->(:WorkItem) (optional but nice for a plan entry point)

(:WorkItem)-[:PARENT_OF]->(:WorkItem) (decomposition tree)

(:WorkItem)-[:CONTRIBUTES_TO]->(:WorkItem) (task → milestone/sub-milestone)

(:WorkItem)-[:CONTRIBUTES_TO]->(:Outcome) (work → outcome)

(:WorkItem)-[:DEPENDS_ON]->(:WorkItem) (blockers)

(:WorkItem)-[:ASSIGNED_TO]->(:Actor)

(:WorkItem)-[:HAS_NOTE]->(:Note)

(:WorkItem)-[:HAS_ARTIFACT]->(:Artifact)

(:Outcome)-[:HAS_ARTIFACT]->(:Artifact) (optional)

(:Event)-[:ABOUT]->(:Project|:WorkItem|:Outcome) (or store target_id only; either works)

(:Event)-[:BY]->(:Actor) (optional if you keep actor_id property)

Key design choice: keep hierarchy (PARENT_OF) separate from meaning (CONTRIBUTES_TO).
That’s the difference from JIRA.

# 3) Memgraph DDL-ish setup (indexes & constraints)

Memgraph supports indexes; uniqueness constraints depend on version/features, but you can at least index IDs and enforce uniqueness at the API layer if needed.

-- Indexes for lookup
CREATE INDEX ON :Project(id);
CREATE INDEX ON :WorkItem(id);
CREATE INDEX ON :WorkItem(project_id);
CREATE INDEX ON :Outcome(id);
CREATE INDEX ON :Outcome(project_id);
CREATE INDEX ON :Artifact(id);
CREATE INDEX ON :Note(id);
CREATE INDEX ON :Actor(id);
CREATE INDEX ON :Event(id);
CREATE INDEX ON :Event(ts);

-- Optional composite-ish speed patterns:
-- project_id + state filtering is common for week/GTD views
CREATE INDEX ON :WorkItem(state);
CREATE INDEX ON :WorkItem(due_at);


If your Memgraph build supports uniqueness constraints, add them for id per label. If not, treat id uniqueness as a domain invariant enforced by the write API.

# 4) Domain invariants (written down now; enforced later)

You can stub these now and hard-enforce later in the facade:

Hierarchy invariants

PARENT_OF must not create cycles (tree/DAG only)

child and parent must share the same project_id

parent must not be done if it has non-done required children (optional policy)

Contribution invariants

CONTRIBUTES_TO must not create cycles (in contribution subgraph)

a WorkItem(kind=task) should contribute to at least one milestone/outcome (policy, not schema)

State invariants (example)

done requires either:

acceptance criteria satisfied (manual flag), OR

linked Outcome.state = verified, OR

explicit waived decision

blocked requires at least one unresolved DEPENDS_ON

Keep these as interface methods (return warnings now).

# 5) Canonical queries (the “views” you want)
A) Plan tree (hierarchy)
MATCH (p:Project {id: $project_id})-[:HAS_ROOT]->(root:WorkItem)
MATCH path = (root)-[:PARENT_OF*0..]->(n:WorkItem)
RETURN root, collect(distinct n) AS nodes, collect(distinct path) AS paths;

B) Milestone progress (meaning-based)

Example: percent of contributing items that are done.

MATCH (m:WorkItem {id: $milestone_id})
MATCH (w:WorkItem)-[:CONTRIBUTES_TO]->(m)
WITH m,
     count(w) AS total,
     sum(CASE WHEN w.state = "done" THEN 1 ELSE 0 END) AS done
RETURN m.id AS milestone_id,
       total,
       done,
       CASE WHEN total = 0 THEN 0.0 ELSE (1.0 * done / total) END AS completion_ratio;

C) Blockers for an item
MATCH (w:WorkItem {id: $id})-[:DEPENDS_ON]->(b:WorkItem)
WHERE b.state <> "done"
RETURN b;

D) “This week” cross-project queue for an actor
MATCH (a:Actor {id: $actor_id})<-[:ASSIGNED_TO]-(w:WorkItem)
WHERE w.state IN ["planned","active","blocked"]
  AND w.due_at >= $start AND w.due_at < $end
RETURN w
ORDER BY w.due_at ASC, w.priority DESC;

E) GTD “Next Actions” (simple heuristic)
MATCH (a:Actor {id: $actor_id})<-[:ASSIGNED_TO]-(w:WorkItem)
WHERE w.state IN ["planned","active"]
  AND NOT (w)-[:DEPENDS_ON]->(:WorkItem {state: "done"})  -- (you'll refine)
RETURN w;


(You’ll refine GTD logic later; the point is: it’s a query projection.)

# 6) Low-level API (storage-first, constraint-light)

Design it as commands + queries so you can later add constraint checks and event logging without breaking callers.

Commands (write)

create_project(id, name, …)

create_work_item(id, project_id, title, kind, …)

set_work_item_state(id, new_state, reason=None)

link_parent(child_id, parent_id)

link_contributes(from_id, to_id) (to WorkItem or Outcome)

link_depends_on(a_id, b_id)

assign(work_item_id, actor_id)

attach_artifact(node_id, artifact_ref, kind, meta)

add_note(node_id, body, tags)

append_event(actor_id, verb, target_id, payload)

Queries (read)

get_plan_tree(project_id)

get_milestone_rollup(milestone_id)

get_contribution_graph(node_id, depth)

get_blockers(node_id)

get_week_view(actor_id, start, end)

get_inbox(actor_id) / get_gtd_view(actor_id)

Implementation detail: even in Layer 1, every command should append an :Event node (or event record). That’s the single best “future-proofing” move for collaboration + agents.

# 7) “Facade” layer: where semantics live

Your Layer 2 should do things like:

compute milestone completion using:

contributions + child completion + optional weights

enforce policies:

“task must contribute to something”

“cannot mark done unless validated”

produce curated views:

“project status report”

“milestones at risk”

“weekly plan across projects”

Critically: the facade never changes the storage shape. It just interprets it.

# 8) Why this works for agents and humans

Agents need:

explicit objects

explicit relations

ability to propose links/states

event history to explain changes

Humans need:

plan view

weekly view

progress that maps to outcomes

This schema supports both without baking agent-isms into the core.


---
If you want, next I can write a Memgraph Cypher “bootstrap” file that:

creates a demo project

creates milestones/tasks/outcomes

links hierarchy + contributions + dependencies

shows the key queries returning sensible results

…so you can immediately validate the model in Memgraph Lab.

yes - plese that would be awesome
```cypher
// ============================================================================
// Memgraph Bootstrap Demo: Goal-directed planning model (Project/WorkItem/Outcome)
// - Creates a demo project with milestones, tasks, sub-milestones
// - Adds contributions + dependencies + assignments
// - Attaches notes + artifacts
// - Appends a small event log
//
// How to use:
// 1) Paste into Memgraph Lab "Query" and run.
// 2) Then run the "VIEW QUERIES" section one-by-one.
// ============================================================================

/* ----------------------------------------------------------------------------
   CLEANUP (optional)
   Uncomment if you want to wipe the graph before seeding.
---------------------------------------------------------------------------- */
// MATCH (n) DETACH DELETE n;

/* ----------------------------------------------------------------------------
   CONSTANTS (edit these if you want)
---------------------------------------------------------------------------- */
WITH
  "proj_demo_001" AS PROJECT_ID,
  "Demo: Productivity Graph Backend" AS PROJECT_NAME,
  "actor_chris" AS ACTOR_CHRIS,
  "agent_planner" AS ACTOR_AGENT
RETURN PROJECT_ID, PROJECT_NAME, ACTOR_CHRIS, ACTOR_AGENT;

/* ----------------------------------------------------------------------------
   CREATE ACTORS
---------------------------------------------------------------------------- */
MERGE (:Actor {id: "actor_chris"})
  ON CREATE SET kind = "human", name = "Chris";

MERGE (:Actor {id: "agent_planner"})
  ON CREATE SET kind = "agent", name = "PlannerAgent";

/* ----------------------------------------------------------------------------
   CREATE PROJECT
---------------------------------------------------------------------------- */
MERGE (p:Project {id: "proj_demo_001"})
  ON CREATE SET
    name = "Demo: Productivity Graph Backend",
    status = "active",
    created_at = datetime(),
    updated_at = datetime();

/* ----------------------------------------------------------------------------
   CREATE ROOT WORK ITEM (optional but convenient)
---------------------------------------------------------------------------- */
MERGE (root:WorkItem {id: "wi_root"})
  ON CREATE SET
    project_id = "proj_demo_001",
    title = "Plan: MVP-ish backend schema + low-level API",
    kind = "milestone",
    state = "active",
    priority = 50,
    created_at = datetime(),
    updated_at = datetime();

MATCH (p:Project {id: "proj_demo_001"}), (root:WorkItem {id: "wi_root"})
MERGE (p)-[:HAS_ROOT]->(root);

/* ----------------------------------------------------------------------------
   CREATE OUTCOMES (measurable end-states)
---------------------------------------------------------------------------- */
MERGE (o1:Outcome {id: "out_schema_api"})
  ON CREATE SET
    project_id = "proj_demo_001",
    title = "Schema + low-level API defined and testable",
    criteria = "Can create/link/query WorkItems and Outcomes; demo queries return expected results.",
    state = "pending",
    created_at = datetime(),
    updated_at = datetime();

MERGE (o2:Outcome {id: "out_views"})
  ON CREATE SET
    project_id = "proj_demo_001",
    title = "Core views exist as queries (plan, weekly, blockers, rollups)",
    criteria = "Cypher queries produce plan tree, milestone rollup, week view, dependency blockers.",
    state = "pending",
    created_at = datetime(),
    updated_at = datetime();

/* ----------------------------------------------------------------------------
   CREATE MILESTONES / SUB-MILESTONES AS WORKITEMS
---------------------------------------------------------------------------- */
MERGE (m1:WorkItem {id: "wi_m1_schema"})
  ON CREATE SET
    project_id = "proj_demo_001",
    title = "Milestone: Domain schema + indexes",
    kind = "milestone",
    state = "active",
    priority = 80,
    created_at = datetime(),
    updated_at = datetime();

MERGE (m2:WorkItem {id: "wi_m2_api"})
  ON CREATE SET
    project_id = "proj_demo_001",
    title = "Milestone: Low-level command/query API",
    kind = "milestone",
    state = "planned",
    priority = 70,
    created_at = datetime(),
    updated_at = datetime();

MERGE (m3:WorkItem {id: "wi_m3_views"})
  ON CREATE SET
    project_id = "proj_demo_001",
    title = "Milestone: Canonical views (queries)",
    kind = "milestone",
    state = "planned",
    priority = 60,
    created_at = datetime(),
    updated_at = datetime();

/* hierarchy: root -> milestones */
MATCH (root:WorkItem {id: "wi_root"})
MATCH (m1:WorkItem {id: "wi_m1_schema"})
MATCH (m2:WorkItem {id: "wi_m2_api"})
MATCH (m3:WorkItem {id: "wi_m3_views"})
MERGE (root)-[:PARENT_OF]->(m1)
MERGE (root)-[:PARENT_OF]->(m2)
MERGE (root)-[:PARENT_OF]->(m3);

/* ----------------------------------------------------------------------------
   CREATE TASKS (leaf work items)
---------------------------------------------------------------------------- */
MERGE (t1:WorkItem {id: "wi_t1_labels"})
  ON CREATE SET
    project_id = "proj_demo_001",
    title = "Define labels: Project, WorkItem, Outcome, Artifact, Note, Actor, Event",
    kind = "task",
    state = "done",
    priority = 70,
    created_at = datetime(),
    updated_at = datetime();

MERGE (t2:WorkItem {id: "wi_t2_edges"})
  ON CREATE SET
    project_id = "proj_demo_001",
    title = "Define relationship types: PARENT_OF, CONTRIBUTES_TO, DEPENDS_ON, ASSIGNED_TO, HAS_NOTE, HAS_ARTIFACT",
    kind = "task",
    state = "active",
    priority = 70,
    created_at = datetime(),
    updated_at = datetime();

MERGE (t3:WorkItem {id: "wi_t3_indexes"})
  ON CREATE SET
    project_id = "proj_demo_001",
    title = "Create indexes for fast lookups (id, project_id, state, due_at)",
    kind = "task",
    state = "planned",
    priority = 60,
    created_at = datetime(),
    updated_at = datetime();

MERGE (t4:WorkItem {id: "wi_t4_commands"})
  ON CREATE SET
    project_id = "proj_demo_001",
    title = "Define command API (create/link/state/assign/attach)",
    kind = "task",
    state = "planned",
    priority = 65,
    created_at = datetime(),
    updated_at = datetime();

MERGE (t5:WorkItem {id: "wi_t5_queries"})
  ON CREATE SET
    project_id = "proj_demo_001",
    title = "Define query API (plan tree, blockers, contributions, week view)",
    kind = "task",
    state = "planned",
    priority = 65,
    created_at = datetime(),
    updated_at = datetime();

MERGE (t6:WorkItem {id: "wi_t6_eventlog"})
  ON CREATE SET
    project_id = "proj_demo_001",
    title = "Add event log node type + append events on writes (stub ok)",
    kind = "task",
    state = "planned",
    priority = 55,
    created_at = datetime(),
    updated_at = datetime();

MERGE (t7:WorkItem {id: "wi_t7_rollup"})
  ON CREATE SET
    project_id = "proj_demo_001",
    title = "Implement milestone rollup query (completion ratio)",
    kind = "task",
    state = "planned",
    priority = 55,
    created_at = datetime(),
    updated_at = datetime();

MERGE (t8:WorkItem {id: "wi_t8_weekview"})
  ON CREATE SET
    project_id = "proj_demo_001",
    title = "Implement 'this week' cross-project view query",
    kind = "task",
    state = "planned",
    priority = 50,
    due_at = datetime() + duration({days: 3}),
    created_at = datetime(),
    updated_at = datetime();

/* hierarchy: milestones -> tasks */
MATCH (m1:WorkItem {id: "wi_m1_schema"})
MATCH (m2:WorkItem {id: "wi_m2_api"})
MATCH (m3:WorkItem {id: "wi_m3_views"})
MATCH (t1:WorkItem {id: "wi_t1_labels"})
MATCH (t2:WorkItem {id: "wi_t2_edges"})
MATCH (t3:WorkItem {id: "wi_t3_indexes"})
MATCH (t4:WorkItem {id: "wi_t4_commands"})
MATCH (t5:WorkItem {id: "wi_t5_queries"})
MATCH (t6:WorkItem {id: "wi_t6_eventlog"})
MATCH (t7:WorkItem {id: "wi_t7_rollup"})
MATCH (t8:WorkItem {id: "wi_t8_weekview"})
MERGE (m1)-[:PARENT_OF]->(t1)
MERGE (m1)-[:PARENT_OF]->(t2)
MERGE (m1)-[:PARENT_OF]->(t3)
MERGE (m2)-[:PARENT_OF]->(t4)
MERGE (m2)-[:PARENT_OF]->(t5)
MERGE (m2)-[:PARENT_OF]->(t6)
MERGE (m3)-[:PARENT_OF]->(t7)
MERGE (m3)-[:PARENT_OF]->(t8);

/* ----------------------------------------------------------------------------
   CONTRIBUTIONS (goal-directed meaning)
   Tasks contribute to milestones; milestones contribute to outcomes.
---------------------------------------------------------------------------- */
MATCH (t1:WorkItem {id: "wi_t1_labels"}), (m1:WorkItem {id: "wi_m1_schema"})
MERGE (t1)-[:CONTRIBUTES_TO]->(m1);

MATCH (t2:WorkItem {id: "wi_t2_edges"}), (m1:WorkItem {id: "wi_m1_schema"})
MERGE (t2)-[:CONTRIBUTES_TO]->(m1);

MATCH (t3:WorkItem {id: "wi_t3_indexes"}), (m1:WorkItem {id: "wi_m1_schema"})
MERGE (t3)-[:CONTRIBUTES_TO]->(m1);

MATCH (t4:WorkItem {id: "wi_t4_commands"}), (m2:WorkItem {id: "wi_m2_api"})
MERGE (t4)-[:CONTRIBUTES_TO]->(m2);

MATCH (t5:WorkItem {id: "wi_t5_queries"}), (m2:WorkItem {id: "wi_m2_api"})
MERGE (t5)-[:CONTRIBUTES_TO]->(m2);

MATCH (t6:WorkItem {id: "wi_t6_eventlog"}), (m2:WorkItem {id: "wi_m2_api"})
MERGE (t6)-[:CONTRIBUTES_TO]->(m2);

MATCH (t7:WorkItem {id: "wi_t7_rollup"}), (m3:WorkItem {id: "wi_m3_views"})
MERGE (t7)-[:CONTRIBUTES_TO]->(m3);

MATCH (t8:WorkItem {id: "wi_t8_weekview"}), (m3:WorkItem {id: "wi_m3_views"})
MERGE (t8)-[:CONTRIBUTES_TO]->(m3);

/* milestones contribute to outcomes */
MATCH (m1:WorkItem {id: "wi_m1_schema"}), (o1:Outcome {id: "out_schema_api"})
MERGE (m1)-[:CONTRIBUTES_TO]->(o1);

MATCH (m2:WorkItem {id: "wi_m2_api"}), (o1:Outcome {id: "out_schema_api"})
MERGE (m2)-[:CONTRIBUTES_TO]->(o1);

MATCH (m3:WorkItem {id: "wi_m3_views"}), (o2:Outcome {id: "out_views"})
MERGE (m3)-[:CONTRIBUTES_TO]->(o2);

/* root contributes to both outcomes */
MATCH (root:WorkItem {id: "wi_root"}), (o1:Outcome {id: "out_schema_api"}), (o2:Outcome {id: "out_views"})
MERGE (root)-[:CONTRIBUTES_TO]->(o1)
MERGE (root)-[:CONTRIBUTES_TO]->(o2);

/* ----------------------------------------------------------------------------
   DEPENDENCIES (blocking)
---------------------------------------------------------------------------- */
MATCH (t4:WorkItem {id: "wi_t4_commands"}), (t2:WorkItem {id: "wi_t2_edges"})
MERGE (t4)-[:DEPENDS_ON]->(t2);

MATCH (t5:WorkItem {id: "wi_t5_queries"}), (t2:WorkItem {id: "wi_t2_edges"})
MERGE (t5)-[:DEPENDS_ON]->(t2);

MATCH (t7:WorkItem {id: "wi_t7_rollup"}), (t5:WorkItem {id: "wi_t5_queries"})
MERGE (t7)-[:DEPENDS_ON]->(t5);

/* ----------------------------------------------------------------------------
   ASSIGNMENTS
---------------------------------------------------------------------------- */
MATCH (c:Actor {id: "actor_chris"})
MATCH (a:Actor {id: "agent_planner"})
MATCH (t2:WorkItem {id: "wi_t2_edges"})
MATCH (t4:WorkItem {id: "wi_t4_commands"})
MATCH (t5:WorkItem {id: "wi_t5_queries"})
MATCH (t8:WorkItem {id: "wi_t8_weekview"})
MERGE (t2)-[:ASSIGNED_TO]->(c)
MERGE (t4)-[:ASSIGNED_TO]->(c)
MERGE (t5)-[:ASSIGNED_TO]->(a)
MERGE (t8)-[:ASSIGNED_TO]->(c);

/* ----------------------------------------------------------------------------
   NOTES + ARTIFACTS (attached to any node)
---------------------------------------------------------------------------- */
MERGE (n1:Note {id: "note_schema"})
  ON CREATE SET
    body = "Keep hierarchy (PARENT_OF) separate from meaning (CONTRIBUTES_TO). This avoids the JIRA epic-as-container trap.",
    tags = ["schema","principle"],
    created_at = datetime();

MERGE (n2:Note {id: "note_events"})
  ON CREATE SET
    body = "Add an append-only Event log early. It makes collaboration + agents + audit/undo vastly easier.",
    tags = ["events","architecture"],
    created_at = datetime();

MERGE (a1:Artifact {id: "art_bootstrap"})
  ON CREATE SET
    kind = "doc",
    ref = "memgraph/bootstrap.cypher",
    meta = "{ \"purpose\": \"seed graph + demo queries\" }",
    created_at = datetime();

MATCH (m1:WorkItem {id: "wi_m1_schema"}), (n1:Note {id: "note_schema"})
MERGE (m1)-[:HAS_NOTE]->(n1);

MATCH (m2:WorkItem {id: "wi_m2_api"}), (n2:Note {id: "note_events"})
MERGE (m2)-[:HAS_NOTE]->(n2);

MATCH (root:WorkItem {id: "wi_root"}), (a1:Artifact {id: "art_bootstrap"})
MERGE (root)-[:HAS_ARTIFACT]->(a1);

/* ----------------------------------------------------------------------------
   EVENT LOG (append-only facts)
---------------------------------------------------------------------------- */
MERGE (e1:Event {id: "evt_001"})
  ON CREATE SET
    ts = datetime(),
    actor_id = "actor_chris",
    verb = "ProjectCreated",
    target_id = "proj_demo_001",
    payload = "{ \"name\": \"Demo: Productivity Graph Backend\" }";

MERGE (e2:Event {id: "evt_002"})
  ON CREATE SET
    ts = datetime(),
    actor_id = "actor_chris",
    verb = "WorkItemStateChanged",
    target_id = "wi_t1_labels",
    payload = "{ \"from\": \"active\", \"to\": \"done\" }";

MERGE (e3:Event {id: "evt_003"})
  ON CREATE SET
    ts = datetime(),
    actor_id = "agent_planner",
    verb = "DependencyAdded",
    target_id = "wi_t4_commands",
    payload = "{ \"depends_on\": \"wi_t2_edges\" }";

MATCH (a:Actor {id: "actor_chris"}), (x:Event {id: "evt_001"})
MERGE (x)-[:BY]->(a);

MATCH (a:Actor {id: "actor_chris"}), (x:Event {id: "evt_002"})
MERGE (x)-[:BY]->(a);

MATCH (a:Actor {id: "agent_planner"}), (x:Event {id: "evt_003"})
MERGE (x)-[:BY]->(a);

/* ============================================================================
   VIEW QUERIES (run these after seeding)
============================================================================ */

/* 1) PLAN TREE: show all nodes reachable from root by PARENT_OF */
//
// MATCH (p:Project {id: "proj_demo_001"})-[:HAS_ROOT]->(root:WorkItem)
// MATCH path = (root)-[:PARENT_OF*0..]->(n:WorkItem)
// RETURN root, collect(DISTINCT n) AS nodes, collect(DISTINCT path) AS paths;

/* 2) MILESTONE ROLLUP: completion ratio for a milestone (based on direct contributors) */
//
// MATCH (m:WorkItem {id: "wi_m1_schema"})
// MATCH (w:WorkItem)-[:CONTRIBUTES_TO]->(m)
// WITH m,
//      count(w) AS total,
//      sum(CASE WHEN w.state = "done" THEN 1 ELSE 0 END) AS done
// RETURN m.id AS milestone_id, m.title AS title, total, done,
//        CASE WHEN total = 0 THEN 0.0 ELSE (1.0 * done / total) END AS completion_ratio;

/* 3) BLOCKERS: unresolved dependencies for a given work item */
//
// MATCH (w:WorkItem {id: "wi_t4_commands"})-[:DEPENDS_ON]->(b:WorkItem)
// WHERE b.state <> "done"
// RETURN w.id AS blocked_item, collect(b.id) AS blockers;

/* 4) CONTRIBUTION GRAPH: what contributes (directly) to the root */
//
// MATCH (root:WorkItem {id: "wi_root"})
// MATCH (w:WorkItem)-[:CONTRIBUTES_TO]->(root)
// RETURN root.id, collect(w.id) AS direct_contributors;

/* 5) WEEK VIEW: due soon items for Chris (actor_chris) */
// (Uses now..now+7d. Adjust as you like.)
//
// MATCH (a:Actor {id: "actor_chris"})<-[:ASSIGNED_TO]-(w:WorkItem)
// WHERE w.state IN ["planned","active","blocked"]
//   AND w.due_at IS NOT NULL
//   AND w.due_at >= datetime()
//   AND w.due_at < (datetime() + duration({days: 7}))
// RETURN w
// ORDER BY w.due_at ASC, w.priority DESC;

/* 6) OUTCOMES: show outcomes and what contributes to them */
//
// MATCH (o:Outcome {project_id: "proj_demo_001"})
// OPTIONAL MATCH (x)-[:CONTRIBUTES_TO]->(o)
// RETURN o.id, o.title, o.state, collect(DISTINCT x.id) AS contributors;
```