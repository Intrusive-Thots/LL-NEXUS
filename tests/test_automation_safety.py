from nexus.core.automation.kill_switch import GlobalKillSwitch,KillSwitchTripped
def test_kill_switch_blocks():
    k=GlobalKillSwitch(); k.trip("test")
    try:k.guard()
    except KillSwitchTripped:pass
    else:assert False
