"""Preserve real titles/parent titles when constructing future MD oracle contexts."""
def source_sections_with_headings(doc, references):
 sections=[];seen=set()
 for ref in references:
  span=doc['spans'][str(ref['id_sp'])];key=span['id_sec']
  if key in seen:continue
  seen.add(key);body=span['text_sec'];headings=[x['text'].strip() for x in span.get('parent_titles',[]) if x.get('text')]
  title=span.get('title','').strip()
  if title and title not in headings:headings.append(title)
  prefix='\n'.join(h for h in headings if h and not body.lstrip().startswith(h))
  sections.append((prefix+'\n'+body).strip())
 return '\n\n'.join(sections)
