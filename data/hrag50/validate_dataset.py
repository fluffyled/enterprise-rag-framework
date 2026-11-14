#!/usr/bin/env python3
"""Verify gold evidence against the exact native-text contents of raw.zip.
Requires: pymupdf, python-docx. Does not OCR or semantically judge answers.
"""
import argparse
import hashlib
import io
import json
import zipfile
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-zip',required=True,type=Path)
    parser.add_argument('--gold',type=Path,default=Path(__file__).with_name('hierarchical_complex_qa_50.jsonl'))
    args=parser.parse_args()
    import fitz
    from docx import Document
    rows=[json.loads(line) for line in args.gold.read_text(encoding='utf-8').splitlines() if line.strip()]
    evidence={e['evidence_id']:e for r in rows for e in r['gold_evidence']}
    with zipfile.ZipFile(args.raw_zip) as z:
        archive={Path(x.filename).name:x for x in z.infolist() if not x.is_dir()}
        doc_cache={}
        for ev in evidence.values():
            name=ev['document_filename']
            if name not in archive:raise AssertionError(f'Missing original: {name}')
            if name not in doc_cache:
                raw=z.read(archive[name]); kind=Path(name).suffix.lower()
                if kind=='.pdf':
                    obj=fitz.open(stream=raw,filetype='pdf')
                    doc_cache[name]=('pdf',[page.get_text(sort=True) for page in obj])
                elif kind=='.docx':
                    doc=Document(io.BytesIO(raw))
                    doc_cache[name]=('docx',[p.text.strip() for p in doc.paragraphs])
                else:raise AssertionError(f'Unsupported evidence file: {name}')
            kind,units=doc_cache[name]
            loc=ev['location']
            n=loc['page']-1 if kind=='pdf' else loc['paragraph_zero_based']
            text=units[n]
            if text[loc['start']:loc['end']]!=ev['evidence_quote']:
                raise AssertionError(f'Evidence mismatch: {ev["evidence_id"]}')
            if hashlib.sha256(text.encode('utf-8')).hexdigest()!=ev['source_text_sha256']:
                raise AssertionError(f'Source unit hash mismatch: {ev["evidence_id"]}')
    ids=[x['id'] for x in rows]
    if len(ids)!=len(set(ids)):raise AssertionError('Duplicate QA ids')
    for row in rows:
        byid={e['evidence_id'] for e in row['gold_evidence']}
        if len(byid)<2:raise AssertionError(f'Not a multi-evidence question: {row["id"]}')
        for f in row['required_facts']:
            if not f['evidence_ids'] or not set(f['evidence_ids'])<=byid:
                raise AssertionError(f'Bad fact evidence refs: {row["id"]}, {f["fact_id"]}')
    print(json.dumps({'status':'PASS','qa':len(rows),'dev':sum(x['split']=='dev' for x in rows),
                      'test':sum(x['split']=='test' for x in rows),
                      'gold_evidence_unique':len(evidence),
                      'gold_facts':sum(len(x['required_facts']) for x in rows),
                      'original_documents_verified':len(doc_cache)},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
