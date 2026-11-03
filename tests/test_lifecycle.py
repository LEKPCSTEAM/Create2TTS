from create2tts.worker.lifecycle import Lifecycle


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class Svc:
    def __init__(self):
        self.unloads = 0

    def unload_models(self):
        self.unloads += 1


def make(timeout_min=1.0, auto_exit=True):
    clock = Clock()
    return Lifecycle(timeout_min, auto_exit, clock), clock, Svc(), []


def test_exit_when_idle_auto_exit_no_web():
    lc, clock, svc, exits = make()
    clock.now += 61
    assert lc.tick(svc, lambda: exits.append(1)) == "exit"
    assert exits == [1]
    assert svc.unloads == 0


def test_unload_once_when_web_client_active():
    lc, clock, svc, exits = make()
    clock.now += 31
    lc.heartbeat()
    clock.now += 30
    assert lc.web_client_active()
    assert lc.tick(svc, lambda: exits.append(1)) == "unload"
    assert lc.tick(svc, lambda: exits.append(1)) == "none"
    assert svc.unloads == 1
    assert exits == []


def test_unload_when_auto_exit_off():
    lc, clock, svc, _ = make(auto_exit=False)
    clock.now += 61
    assert lc.tick(svc, lambda: None) == "unload"
    assert lc.tick(svc, lambda: None) == "none"


def test_heartbeat_expires_after_90s():
    lc, clock, _, _ = make()
    lc.heartbeat()
    clock.now += 91
    assert not lc.web_client_active()


def test_none_before_timeout():
    lc, clock, svc, _ = make()
    clock.now += 30
    assert lc.tick(svc, lambda: None) == "none"


def test_none_while_job_running():
    lc, clock, svc, _ = make()
    lc.begin_job()
    clock.now += 600
    assert lc.tick(svc, lambda: None) == "none"
    assert lc.idle_s() == 0


def test_timeout_zero_exits_right_after_job():
    lc, clock, svc, exits = make(timeout_min=0)
    lc.begin_job()
    clock.now += 5
    lc.end_job()
    assert lc.tick(svc, lambda: exits.append(1)) == "exit"


def test_idle_s_counts_from_last_job_end():
    lc, clock, _, _ = make()
    lc.begin_job()
    clock.now += 10
    lc.end_job()
    clock.now += 7
    assert lc.idle_s() == 7


def test_unload_again_after_new_job():
    lc, clock, svc, _ = make(auto_exit=False)
    clock.now += 61
    assert lc.tick(svc, lambda: None) == "unload"
    lc.begin_job()
    lc.end_job()
    clock.now += 61
    assert lc.tick(svc, lambda: None) == "unload"
    assert svc.unloads == 2
