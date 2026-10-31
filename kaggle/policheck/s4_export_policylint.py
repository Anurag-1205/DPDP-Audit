# -*- coding: utf-8 -*-
"""Python 2.7, run in PolicyLint's code directory (/src) after PatternExtractionNotebook.py (S4, WP-3.6).

  python2 s4_export_policylint.py OUT.json

Exports every statement PolicyLint extracted from /ext/output/policy/*.pickle, both raw and
normalised by PolicyLint's own loadPrivacyPolicyResults (entity and data resolved to its
ontologies, user/you statements and its negation filters applied), plus the two ontologies'
terms and edges, as JSON. Nothing here changes what PolicyLint extracts.
"""
from __future__ import unicode_literals
import codecs
import glob
import json
import os
import sys

import dill as pickle
import spacy

import Consistency as con
import ConsistencyAnalysis as ca


class NoDB(object):
    """loadPrivacyPolicyResults also writes to PoliCheck's database; S4 needs only the statements."""

    def __getattr__(self, name):
        return lambda *args, **kwargs: None


def main(out_path):
    con.init(dataOntologyFilename='data_ontology.pickle', entityOntologyFilename='entity_ontology.pickle')
    if 'we' not in con.Entity.ontology.nodes():   # loadPrivacyPolicyResults maps the first party to 'we'
        raise SystemExit('entity ontology has no "we" node: every first-party statement would be dropped')
    nlp = spacy.load('/ext/NlpFinalModel')
    segments = {}
    for path in sorted(glob.glob('/ext/output/policy/*.pickle')):
        name = os.path.basename(path)[:-len('.pickle')]
        if name.endswith('.txt'):
            name = name[:-len('.txt')]
        raw = [[ca.ensureUnicode(x) for x in s] for s in pickle.load(open(path, 'rb'))]
        norm = ca.loadPrivacyPolicyResults(path, name, NoDB(), nlp, '1')
        segments[name] = {'raw': raw, 'statements': [[ca.ensureUnicode(x) for x in s] for s in norm]}
    ontology = {'data_root': con.DataObject.root, 'entity_root': con.Entity.root,
                'data_edges': [list(e) for e in con.DataObject.ontology.edges()],
                'entity_edges': [list(e) for e in con.Entity.ontology.edges()],
                'data_nodes': sorted(con.DataObject.ontology.nodes()),
                'entity_nodes': sorted(con.Entity.ontology.nodes())}
    with codecs.open(out_path, 'w', 'utf-8') as f:
        f.write(json.dumps({'segments': segments, 'ontology': ontology}, ensure_ascii=False))
    print('exported {} segments, {} raw and {} normalised statements'.format(
        len(segments), sum(len(v['raw']) for v in segments.values()),
        sum(len(v['statements']) for v in segments.values())))


if __name__ == '__main__':
    main(sys.argv[1])
