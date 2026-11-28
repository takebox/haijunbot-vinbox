# -*- coding: utf-8 -*-
"""HaijunBot evaluation adapter layer (Terminal-Bench / Harbor integration).

Wraps HaijunBot as Harbor's ``BaseInstalledAgent``, so it can run as
an evaluation Agent for Terminal-Bench 2.0.

Harbor is a lazy dependency: this package (``haijunbot_eval``) can be safely imported by the
main HaijunBot project without triggering the harbor dependency; ``harbor`` is only required
when Harbor actually loads the ``haijunbot_eval.harbor_agent`` module.

Usage (on an evaluation machine with Docker): :

    harbor run --dataset terminal-bench@2.0 \\
        -a haijunbot_eval.harbor_agent:HaijunBotInstalledAgent \\
        --ae OPENAI_API_KEY=<your-key>
"""
