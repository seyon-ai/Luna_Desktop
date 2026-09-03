from __future__ import annotations

from luna.app.application import Application


def test_application_wiring(tmp_home):
    app = Application(tmp_home)
    assert app.paths.root == tmp_home.resolve()
    assert app.paths.database.exists()
    assert app.settings_manager.path.exists()
    # tool registry contains the core set
    names = {t.name for t in app.tools.all()}
    assert "read_file" in names
    assert "run_command" in names
    assert "browser_navigate" in names
    assert app.memory.db is not None
    app.shutdown()


def test_agent_task_via_application(tmp_home):
    app = Application(tmp_home)

    def fake_model(messages, tools):
        return {"type": "complete", "message": "Done without side effects."}

    task = app.create_agent_task("Say hello", model_fn=fake_model)
    finished = app.tasks.wait(task.id, timeout=10)
    assert finished is not None
    assert finished.status.value == "COMPLETED"
    # conversation-ish activity is not recorded without explicit user message
    assert app.memory.list_conversations() == []
    app.shutdown()
