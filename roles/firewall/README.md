Firewall
========

This role manages the iptables rules.

Usage
-----

You role must contains a `templates/iptables.j2` file with your iptables rules.

In your role's meta, add a dependency to this role using the syntax described below.

```yaml
# my_role/meta/main.yml
  - role: firewall
    caller_name: my_role
```

When you will run the playbook, the rules will be applied.

Rules template example
----------------------

```
# Firewall rules for the 'nginx' role
*filter
:nginx_in - [0:0]
-I INPUT -j nginx_in
-A nginx_in -p tcp -m tcp --dport 80 -j ACCEPT
COMMIT
```
