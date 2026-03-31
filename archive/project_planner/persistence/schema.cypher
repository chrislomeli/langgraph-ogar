-- Project-Planner: Memgraph indexes
-- Run once after database creation.

CREATE INDEX ON :Project(id);
CREATE INDEX ON :WorkItem(id);
CREATE INDEX ON :WorkItem(project_id);
CREATE INDEX ON :WorkItem(state);
CREATE INDEX ON :WorkItem(due_at);
CREATE INDEX ON :Outcome(id);
CREATE INDEX ON :Outcome(project_id);
CREATE INDEX ON :Artifact(id);
CREATE INDEX ON :Artifact(project_id);
CREATE INDEX ON :Note(id);
CREATE INDEX ON :Note(project_id);
CREATE INDEX ON :Actor(id);
CREATE INDEX ON :Event(id);
CREATE INDEX ON :Event(ts);
