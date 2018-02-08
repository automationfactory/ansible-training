#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
from distutils.version import LooseVersion


def generate_docker_rules(save):
    rules = []
    for line in save.split('\n'):
        line = line.strip()
        if not line:
            continue

        if line.lower().find('docker') == -1:
            continue

        # Skip lines which don't add a new rule
        if not line.startswith('-A'):
            continue

        # ignore custom rules
        for chain in ['PREROUTING', 'POSTROUTING', 'OUTPUT', 'DOCKER',
                      'DOCKER-ISOLATION', 'FORWARD']:
            if line.startswith('-A ' + chain):
                break
        else:
            continue

        # Add it to the nat table if required
        for chain in ['PREROUTING', 'POSTROUTING', 'OUTPUT', 'DOCKER',
                      'DOCKER-ISOLATION']:
            if line.startswith('-A ' + chain):
                line = '-t nat ' + line

        rules.append(line)

    if rules:
        rules.insert(0, '-t nat -N DOCKER')
        rules.insert(0, '-N DOCKER')
        rules.insert(0, '-t nat -N DOCKER-ISOLATION')
        rules.insert(0, '-N DOCKER-ISOLATION')
    return rules


def main():
    global module
    module = AnsibleModule(
        argument_spec=dict(
            state=dict(default='reloaded', choices=['reloaded'])
        )
    )
    facts = ansible_facts(module, [])

    state = module.params['state']

    if state != 'reloaded':
        module.fail_json(msg="unsupported state '%s'" % state)

    rules_directory = '/etc/iptables.d'

    if not os.path.exists(rules_directory):
        module.fail_json(
            msg="the rules directory (%s) doesn't exist" % rules_directory)

    def is_common(a, b):
        if a == 'common':
            return -1
        elif b == 'common':
            return 1
        else:
            return 0

    rules = sorted(os.listdir(rules_directory), cmp=is_common)
    if not rules:
        module.exit_json(changed=False, msg="no rules to apply")

    _, save_out, _ = module.run_command("iptables-save", check_rc=True)
    save_out = re.sub(r'(?m)^[#:].*', '', save_out)

    docker_rules = generate_docker_rules(save_out)

    _, global_stdout, global_stderr = module.run_command(
        "/sbin/iptables-restore -v"
        " < /etc/iptables.d/%s" % rules[0],
        check_rc=True,
        use_unsafe_shell=True)

    if len(rules) > 1:
        for rule in rules[1:]:
            _, stdout, stderr = module.run_command(
                "/sbin/iptables-restore -v --noflush"
                " < /etc/iptables.d/%s" % rule,
                check_rc=True,
                use_unsafe_shell=True)
            global_stdout = '\n'.join([global_stdout.strip(), stdout.strip()])
            global_stderr = '\n'.join([global_stderr.strip(), stderr.strip()])

    cmd = None
    if facts['distribution'] in ['CentOS', 'RedHat']:
        cmd = "service iptables save"
    elif facts['distribution'] == 'Debian' and LooseVersion(facts['distribution_major_version']) <= LooseVersion('7'):
        cmd = "service iptables-persistent save"
    elif facts['distribution'] == 'Debian' and LooseVersion(facts['distribution_major_version']) >= LooseVersion('8'):
        cmd = "service netfilter-persistent save"

    if cmd:
        _, stdout, stderr = module.run_command(cmd, check_rc=True)
        global_stdout = '\n'.join([global_stdout.strip(), stdout.strip()])
        global_stderr = '\n'.join([global_stderr.strip(), stderr.strip()])
    else:
        module.fail_json(
            msg="the rules are not persistent because '%s' is not supported"
                % facts['distribution'])

    for docker_rule in docker_rules:
        _, stdout, stderr = module.run_command("iptables " + docker_rule,
                                               check_rc=True)
        global_stdout = '\n'.join([global_stdout.strip(), stdout.strip()])
        global_stderr = '\n'.join([global_stderr.strip(), stderr.strip()])

    _, save_end_out, _ = module.run_command("iptables-save", check_rc=True)
    save_end_out = re.sub(r'(?m)^[#:].*', '', save_end_out)

    module.exit_json(changed=(save_out != save_end_out),
                     stdout=global_stdout.strip(),
                     stderr=global_stderr.strip(),
                     msg="the rules '%s' have been applied" % ', '.join(rules))


from ansible.module_utils.basic import *
from ansible.module_utils.facts import *

main()
