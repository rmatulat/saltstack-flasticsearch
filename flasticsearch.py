# -*- coding: utf-8 -*-
'''
Return data to an elasticsearch server for indexing.

:maintainer:    rall0r@posteo.de
:maturity:      New
:depends:       `elasticsearch-py <http://elasticsearch-py.readthedocs.org/en/latest/>`_
:platform:      all

DISCLAIMER:
This is a modifies version of the original salt elasticsearch returner!


To enable this returner the elasticsearch python client must be installed
on the desired minions (all or some subset).

Please see documentation of :mod:`elasticsearch execution module <salt.modules.elasticsearch>`
for a valid connection configuration.

.. warning::

        The index that you wish to store documents will be created by Elasticsearch automatically if
        doesn't exist yet. It is highly recommended to create predefined index templates with appropriate mapping(s)
        that will be used by Elasticsearch upon index creation. Otherwise you will have problems as described in #20826.

You may want to store some grain values as well. To do so you can define a list of grains in your minion config:

.. code-block:: yaml

    es_grains:
      - location
      - patchgroup
      - saltversion
      - roles
      - osfinger

To use the returner per salt call:

.. code-block:: bash

    salt '*' test.ping --return flasticsearch

In order to have the returner apply to all minions:

.. code-block:: yaml

    ext_job_cache: flasticsearch
'''

from __future__ import absolute_import

# Import Python libs
from datetime import tzinfo, datetime, timedelta
import logging
import json

# Import Salt libs
import salt.utils.jid

__virtualname__ = 'flasticsearch'

log = logging.getLogger(__name__)


def __virtual__():
    return __virtualname__


def returner(ret):
    '''
    ret['return'] always look different - for whatever reason.
    So the upcoming code is an unreliable, hard to read mess I never took to
    much efford in.
    I am sorry.
    '''
    job_fun = ret['fun']
    job_fun_escaped = job_fun.replace('.', '_')
    job_id = ret['jid']
    job_success = True if ret['return'] else False
    job_retcode = ret.get('retcode', 1)

    # Read our grains to store in ES 
    es_grains = __salt__['config.option']('es_grains', [])

    custom_data = {}

    for es_grain in es_grains:
        custom_data[es_grain] = __salt__['grains.get'](es_grain, 'notset')

    index = 'salt-{0}'.format(job_fun_escaped)
    # index = 'salt-{0}-{1}'.format(job_fun_escaped, datetime.date.today().strftime('%Y.%m.%d')) #TODO prefer this? #TODO make it configurable!
    functions_blacklist = __salt__['config.option']('elasticsearch:functions_blacklist', [])
    doc_type_version = __salt__['config.option']('elasticsearch:doc_type', 'default')

    if job_fun in functions_blacklist:
        log.info(
            'Won\'t push new data to Elasticsearch, job with jid={0} and function={1} which is in the user-defined list of ignored functions'.format(
                job_id, job_fun))
        return

    index_exists = __salt__['elasticsearch.index_exists'](index)

    if not index_exists:
        number_of_shards = __salt__['config.option']('elasticsearch:number_of_shards', 1)
        number_of_replicas = __salt__['config.option']('elasticsearch:number_of_replicas', 0)

        index_definition = {'settings': {'number_of_shards': number_of_shards, 'number_of_replicas': number_of_replicas}}
        __salt__['elasticsearch.index_create']('{0}-v1'.format(index), index_definition)
        __salt__['elasticsearch.alias_create']('{0}-v1'.format(index), index)

    class UTC(tzinfo):
        def utcoffset(self, dt):
            return timedelta(0)

        def tzname(self, dt):
            return 'UTC'

        def dst(self, dt):
            return timedelta(0)

    utc = UTC()

    items = ret['return'] if ret['return'] else False
    data = {}

    if isinstance(items, dict):
        for item in items:

            data = {
                '@timestamp': datetime.now(utc).isoformat(),
                'success': job_success,
                'minion': ret['id'],
                'fun': ret['fun'],
                'fun_args': ','.join(ret['fun_args']),
                'jid': job_id,
                'retcode': job_retcode
            }

            item_blacklist = ['comment', 'changes', 'result']

            if item not in item_blacklist:
                data['item'] = item
                try:
                    data['result'] = 0 if items[item]['result'] is True else 1
                except:
                    data['result'] = ret['retcode']

                try:
                    data['comment'] = items[item]['comment']
                    data['result'] = 0 if items[item]['result'] is True else 1

                    changes = []
                    for key, value in items[item]['changes'].items():
                        changes.append('Item: {0}, New Value: {1}, Old Value {2}'.format(
                            key,
                            items[item]['changes'][key]['new'],
                            items[item]['changes'][key]['old']
                        ))
                    data['changes'] = ', '.join(changes)
                except:
                    data['comment'] = str(items[item])
                finally:
                    pass

            elif item in item_blacklist:
                try:
                    data['result'] = 0 if items['result'] is True else 1

                    changes = []
                    for key, value in items['changes'].items():
                        changes.append('Item: {0}, New Value: {1}, Old Value {2}'.format(
                            key,
                            items['changes'][key]['new'],
                            items['changes'][key]['old']
                        ))
                    data['changes'] = ', '.join(changes)
                except:
                    pass

            else:
                data['result'] = ret['retcode']
                data['comment'] = str(item)

            data.update(custom_data)

            __salt__['elasticsearch.document_create'](index=index, doc_type=doc_type_version, body=json.dumps(data))

    elif isinstance(items, list):
        data = {
            '@timestamp': datetime.now(utc).isoformat(),
            'success': job_success,
            'minion': ret['id'],
            'fun': ret['fun'],
            'fun_args': ','.join(ret['fun_args']),
            'jid': job_id,
            'comment': ', '.join(items),
            'result': ret['retcode'],
            'retcode': job_retcode
        }

        data.update(custom_data)
        __salt__['elasticsearch.document_create'](index=index, doc_type=doc_type_version, body=json.dumps(data))
    else:
        data = {
            '@timestamp': datetime.now(utc).isoformat(),
            'success': job_success,
            'minion': ret['id'],
            'fun': ret['fun'],
            'fun_args': ','.join(ret['fun_args']),
            'jid': job_id,
            'result': ret['retcode'],
            'comment': items,
            'retcode': job_retcode
        }

        data.update(custom_data)
        __salt__['elasticsearch.document_create'](index=index, doc_type=doc_type_version, body=json.dumps(data))

def prep_jid(nocache=False, passed_jid=None):  # pylint: disable=unused-argument
    '''
    Do any work necessary to prepare a JID, including sending a custom id
    '''
    return passed_jid if passed_jid is not None else salt.utils.jid.gen_jid()


def save_load(jid, load):
    '''
    Save the load to the specified jid id

    .. versionadded:: 2015.8.1
    '''
    index = __salt__['config.option']('elasticsearch:master_job_cache_index', 'salt-master-job-cache')
    doc_type = __salt__['config.option']('elasticsearch:master_job_cache_doc_type', 'default')

    index_exists = __salt__['elasticsearch.index_exists'](index)
    if not index_exists:
        number_of_shards = __salt__['config.option']('elasticsearch:number_of_shards', 1)
        number_of_replicas = __salt__['config.option']('elasticsearch:number_of_replicas', 0)

        index_definition = {'settings': {'number_of_shards': number_of_shards, 'number_of_replicas': number_of_replicas}}
        __salt__['elasticsearch.index_create']('{0}-v1'.format(index), index_definition)
        __salt__['elasticsearch.alias_create']('{0}-v1'.format(index), index)

    data = {
        'jid': jid,
        'load': load,
    }

    ret = __salt__['elasticsearch.document_create'](index=index, doc_type=doc_type, id=jid, body=json.dumps(data))


def get_load(jid):
    '''
    Return the load data that marks a specified jid

    .. versionadded:: 2015.8.1
    '''
    index = __salt__['config.option']('elasticsearch:master_job_cache_index', 'salt-master-job-cache')
    doc_type = __salt__['config.option']('elasticsearch:master_job_cache_doc_type', 'default')

    data = __salt__['elasticsearch.document_get'](index=index, id=jid, doc_type=doc_type)
    if data:
        return json.loads(data)
    return {}
