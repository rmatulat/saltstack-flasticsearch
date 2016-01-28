## What is it?

This is a custom elasticsearch returner for [Saltstack](https://github.com/saltstack/salt).

## What is required for using this?

It depends on [elasticsearch-py](http://elasticsearch-py.readthedocs.org/en/latest/)
The `elasticsearch-py` module has to be installed on any minion that should return its data
to your elasticsearch instance.

## How to install

Create a `_returners` folder in one of your salt `file_roots`, for example under `/srv/salt/base/`
and copy the flasticsearch.py in it.

That run `salt '*' saltutil.sync_all` from the master to synchronise your custom returner to all of
your minions.

You have to add the following elasticsearch parameters to your minion config:

```
elasticsearch:
  hosts:
    - 'salt'
  index: 'salt'
  number_of_shards: 1
  number_of_replicas: 1
```

## How to use it

```
salt 'minion' test.ping --return flasticsearch
```

## Disclaimer

This returner is nothing more than a modified version of the original elasticsearch returner, written by 
Jurnell Cockhren <jurnell.cockhren@sophicware.com> and Arnold Bechtoldt <mail@arnoldbechtoldt.com>

## Why a modified elasticsearch returner

We found that the original returner returns data that is poorly searchable and hard to analyse.
We need every single state in a single document to do some visualisation in kibana.
