#!/usr/bin/env python

from pprint import pformat
import os, os.path, sys, csv, re, itertools, datetime, subprocess, glob, textwrap
from collections import OrderedDict
import xml.etree.ElementTree
import urllib.parse, webbrowser

"""

Input
-----

Place Name, Place Body-text
<empty column>, Destination Body-text, Destination Name

"""

def slugify(name,dedup=False):
  slug = re.sub(r'[^A-Za-z0-9-]','',re.sub(r' +','-',name.lower().strip()))
  #if dedup:
  #  while slug in slugify.slugs:
  #    slug = re.sub(r'(-([0-9]+))?$',lambda mo: '-0' if mo.lastindex is None else '-{}'.format(int(mo.group(2))+1),slug)
  slugify.slugs[slug] = name
  slugify.names[name] = slug
  return slug
slugify.slugs = {}
slugify.names = {}

def key_updater(row):
  if row[0]:
    new_key = slugify(row[0])
    assert new_key not in key_updater.past_keys
    key_updater.past_keys.append(key_updater.current_key)
    key_updater.current_key = new_key
  return key_updater.current_key
key_updater.current_key = None
key_updater.past_keys = []

def parse_csv(rows,root):
  nodes = {}
  for k, g in itertools.groupby(rows, key_updater):
    g = list(g)
    g[0][0] = slugify(g[0][0])
    #for i, edge in enumerate(g[1:]):
    #  if i and len(edge) > 2 and edge[2]:
    #    g[i][2] = slugify(g[i][2])
    assert k not in nodes
    nodes[k] = (g[0][1],OrderedDict((slugify(row[2]),row[1]) for row in g[1:]))
  if root is None:
    roots = set(nodes.keys())
    for node in nodes.values():
      for destination in node[1].keys():
        assert destination in nodes.keys(), "{} not in {}".format(*map(pformat,[destination,nodes]))
        roots.remove(destination)
    assert len(roots) == 1
    root = roots.pop()
  else:
    root = slugify.names[root]
  return nodes, root

hell = Exception()

def write_html(nodes, root, slugs, directory):
  rootify = lambda name: name if name != root else 'index'
  for name, node in nodes.items():
    filename = os.path.join(directory,rootify(name)+'.html')
    b = xml.etree.ElementTree.TreeBuilder()
    b.start('html'); b.start('head');
    b.start('link',{'rel':'stylesheet','href':'http'+'://cdn.jsdelivr.net/bootstrap/3.0.1/css/bootstrap.css'}); b.end('link')
    b.start('link',{'rel':'stylesheet','href':'http'+'://cdn.jsdelivr.net/bootstrap/3.0.1/css/bootstrap-theme.css'}); b.end('link')
    b.start('title'); b.data('CYOA'); b.end('title')
    b.end('head')
    b.start('body')
    b.start('div',{'class':'container'})
    b.start('header',{'class':'page-header'})
    b.start('h1'); b.data('CYOA'); b.end('h1')
    b.end('header')
    b.start('div',{'class':'panel panel-default'})
    b.start('p',{'class':'panel-body'}); b.data(node[0]); b.end('p')
    b.end('div')
    if node[1].items():
      b.start('section',{'class':'list-group'})
      for slug, description in node[1].items():
        b.start('a',{'class':'list-group-item','href':slug+'.html'})
        b.data(description)
        b.end('a')
      b.end('section')
    b.start('hr'); b.end('hr')
    b.start('footer',{'class':'well'})
    b.start('p',{'class':'pull-right'})
    b.start('a',{'href':'output.gv.png'})
    b.data('Visual overview')
    b.end('a')
    b.end('p')
    b.start('p'); b.start('small')
    b.data('System is © 2013 Milo Mirate.')
    b.start('br'); b.end('br')
    b.data('Content is © 2013 Milo Mirate, Joy Zhang and Kevin Christopher.')
    b.end('small'); b.end('p')
    b.end('footer')
    b.end('div')
    b.end('body')
    b.end('html')
    open(filename,'w').write('<!DOCTYPE html>\n'+xml.etree.ElementTree.tostring(b.close(),encoding='unicode'))

def write_graphviz(nodes, slugs, directory):
  gv_slug = lambda slug: re.sub(r'[-]+','_',slug)
  gv_label_escape = lambda text: re.sub('\n',r'\n',re.sub(r'[{}|<>]',lambda m:'\\'+m.group(0),text))
  output_graphviz = [['digraph','house','{']]
  output_graphviz.append(['node','[shape=record];'])
  for name, node in nodes.items():
    output_graphviz.append([gv_slug(name),'[label="{{{}}}"];'.format(re.sub(r'"','&quot;',
          ''+slugs[name]+' | '+gv_label_escape(textwrap.fill(node[0],50))+'| {'+' | '.join(
            '<c{}> {}'.format(i,textwrap.fill(gv_label_escape(v),20)) for i, v in enumerate(node[1].values())
          )+'}'
        ))
      ])
  for name, node in nodes.items():
    for i, k in enumerate(node[1].keys()):
      output_graphviz.append(['{}:c{}'.format(gv_slug(name),i),'->','{}'.format(gv_slug(k)),';'])
  output_graphviz.append(['}'])
  filename = os.path.join(directory,'output.gv')
  open(filename,'w').write('\n'.join(' '.join(row) for row in output_graphviz))
  try:
    subprocess.check_call(['dot','-Tpng','-O',filename])
  except FileNotFoundError:
    subprocess.check_call([list(glob.glob('graphviz-*/release/bin/dot.exe'))[0],'-Tpng','-O',filename])

class UserCausedFNFError(Exception):
  pass

def compile(filename, output_dir):
  try:
    rows = list(filter(bool,csv.reader(sys.stdin if not filename else open(filename ,newline=''))))
  except FileNotFoundError as e:
    raise UserError(e)
  root = None
  try:
    if rows[0][3].lower().startswith('start'): root = rows[0][4]
  except IndexError: pass
  nodes, root = parse_csv(rows[1:],root)
  write_html(nodes,root,slugify.slugs,output_dir)
  write_graphviz(nodes,slugify.slugs,output_dir)

from tkinter import *
from tkinter import ttk, filedialog, messagebox

def refresh_caches():
  key_updater.current_key = None
  key_updater.past_keys = []
  slugify.slugs = {}
  slugify.names = {}

def gui_compile(filename,directory,status,**kwargs):
  trouble = lambda: status.set('Problem encountered at '+str(datetime.datetime.now()))
  success = lambda: status.set('Compilation finished at '+str(datetime.datetime.now()))
  try:
    refresh_caches()
    compile(filename.get(), directory.get())
    #webbrowser.open_new(
    #  'https://chart.googleapis.com/chart?' +
    #  urllib.parse.urlencode({'chl':dot_text, 'cht':'gv'})
    #  )
  except UserCausedFNFError:
    messagebox.showinfo(message='Input file not found.\n\nTry re-exporting it from Google Drive.')
    trouble()
  except BaseException as e:
    import traceback
    messagebox.showinfo(
      message="An error of some kind has occured. Details below. Please inform the developer.",
      detail=traceback.format_exc()
    )
    trouble()
  else:
    if "remove_on_success" in kwargs and kwargs["remove_on_success"].get():
      os.unlink(filename.get())
    success()
  finally:
    refresh_caches()

  return None


def main():

  if len(sys.argv) == 3:
    compile(*sys.argv[1:])
    sys.exit(0)

  root = Tk()
  root.title("Choose-Your-Own-Adventure Compiler, Version 1")
  root.columnconfigure(0, weight=1)
  root.rowconfigure(0, weight=1)
  filename = StringVar()
  directory = StringVar()
  status = StringVar()
  remove_on_success = IntVar()
  remove_on_success.set(1)

  mainframe = ttk.Frame(root, padding="3 3 12 12")
  mainframe.grid(column=0, row=0, sticky=(N, W, E, S))
  mainframe.columnconfigure(0, weight=1)
  mainframe.rowconfigure(0, weight=1)
  gui_compile_cmd = lambda: gui_compile(filename,directory,status,remove_on_success=remove_on_success)
  if len(sys.argv) > 1: filename.set(sys.argv[1])
  directory.set(os.curdir)

  def change_directory(e):
    root.focus()
    directory.set(filedialog.askdirectory(
      initialdir=directory.get(),title="Where to place output files?"
    ))

  def change_filename(e):
    root.focus()
    filename.set(filedialog.askopenfilename(
      initialfile=os.path.basename(filename.get()),
      initialdir=os.path.dirname(filename.get()),
      filetypes=[("CSV Files",".csv")]
    ))

  directory_entry = ttk.Entry(mainframe, textvariable=directory)
  directory_entry.grid(column=1, row=1, columnspan=2, sticky=(W,E))
  ttk.Label(mainframe, text='Output location:').grid(column=0, row=1, sticky=E)
  directory_entry.bind('<FocusIn>', change_directory)

  filename_entry = ttk.Entry(mainframe, textvariable=filename)
  filename_entry.grid(column=1, row=0, columnspan=2, sticky=(W,E))
  ttk.Label(mainframe, text='CSV input file:').grid(column=0, row=0, sticky=E)
  filename_entry.bind('<FocusIn>', change_filename)

  ros_check = ttk.Checkbutton(mainframe, text='Remove input file upon successful compilation', variable=remove_on_success)
  ros_check.grid(column=1,columnspan=2,sticky=W)

  ttk.Button(mainframe, text='Compile', command=gui_compile_cmd).grid(column=1, row=3, sticky=W)
  ttk.Label(mainframe, textvariable=status).grid(column=2, row=3, sticky=E)

  for child in mainframe.winfo_children(): child.grid_configure(padx=5, pady=5)
  mainframe.columnconfigure(0,weight=1)
  mainframe.columnconfigure(1,weight=10000)
  mainframe.rowconfigure('all',weight=1)
  root.bind('<Return>', gui_compile_cmd)

  root.mainloop()

if __name__ == '__main__': main()

