"""Live delay sources, by name. Each is a class implementing live.LiveSource.

None is registered yet: whether we use an official feed or Infofer's public pages
is still being decided (see README, "Live data").
"""
SOURCES: dict[str, type] = {}
