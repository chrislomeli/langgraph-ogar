from starter.model.project import Project

from ulid import ULID

def goal_prompt():
    """

    :return:
    """

def create_new_project(title: str):
    p = Project(
        pid=str(ULID()),
        title=title,
        # non_goals=["Not building a sellable multi-user commercial product"],
    )


def add_new_user_goals():
    """
        p = Project(
        pid="proj_agentic_planner",
        title="Agentic Project Planning Tool (Demo)",
        non_goals=["Not building a sellable multi-user commercial product"],
    )
    todo:
       - if there is not project - ask for the project name
       - get the project goals from the data store
       - dump the goals to the user
       - let the user to add, remove, edit, goals any new goals
       -
    :return:
    """



def update_existing_user_goals():
    """
    todo:
       - if there is not project - ask for the project name
       - get the project goals from the data store
       - dump the goals to the user
       - let the user to add, remove, edit, goals any new goals
       -
    :return:
    """