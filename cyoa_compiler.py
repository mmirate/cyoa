#!/usr/bin/env python

from pprint import pformat
import os, os.path, sys, csv, re, itertools, datetime, subprocess, glob, textwrap
from collections import OrderedDict, namedtuple
import xml.etree.ElementTree
import urllib.parse, webbrowser

sys.path.insert(0,os.path.join(sys.path[0],'Python-Markdown'))
import markdown

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

Page = namedtuple('Page', ['name','description','edges'])
Edge = namedtuple('Edge', ['parent','destination','description'])

class DoneWithThisGroup(Exception): pass

def parse_csv(rows,root):
  nodes = {}
  for kay, gee in itertools.groupby(rows, key_updater):
    try:
      def process_group(k,g):
        g = list(g)
        #g[0][0] = slugify(g[0][0])
        #for i, edge in enumerate(g[1:]):
        #  if i and len(edge) > 2 and edge[2]:
        #    g[i][2] = slugify(g[i][2])
        #assert k==slugify(g[0][0]), "{}!={}".format(k,slugify(g[0][0]))
        assert k not in nodes
        k=slugify(g[0][0])
        assert k not in nodes
        nodes[k] = Page(name=k,description=g[0][1],edges=[Edge(parent=k,destination=slugify(row[2] if len(row)>=3 and row[2] else row[1]),description=row[1]) for row in g[1:]])
        #print(pformat(list(map(lambda x: x.description,nodes[k].edges))))
        #(g[0][1],OrderedDict((slugify(row[2]),row[1]) for row in g[1:]))
      gee = list(gee)
      for row in gee:
        if "<#>" in "".join(row):
          for i in [1,2]:
            expand = lambda s: re.sub(r'<#>',str(i),s)
            process_group(kay,map(lambda row: list(map(expand,row)),gee))
          raise DoneWithThisGroup()
      process_group(kay,gee)
    except DoneWithThisGroup:
      pass
  if root is None:
    roots = set(nodes.keys())
    for node in nodes.values():
      for edge in node.edges:
        assert edge.destination in nodes.keys(), "{} not in {}".format(*map(pformat,[edge.destination,nodes]))
        roots.remove(edge.destination)
    assert len(roots) == 1
    root = roots.pop()
  else:
    root = slugify.names[root]
  return nodes, root

def write_html(nodes, root, slugs, directory):
  title = slugs[root] if root else 'CYOA'
  rootify = lambda name: name if name != root else 'index'
  for name, node in nodes.items():
    filename = os.path.join(directory,rootify(name)+'.html')
    b = xml.etree.ElementTree.TreeBuilder()
    b.start('html'); b.start('head');
    b.start('link',{'rel':'stylesheet','href':'http'+'://cdn.jsdelivr.net/bootstrap/3.0.2/css/bootstrap.css'}); b.end('link')
    #b.start('link',{'rel':'stylesheet','href':'http'+'://cdn.jsdelivr.net/bootstrap/3.0.2/css/bootstrap-theme.css'}); b.end('link')
    b.start('title'); b.data(title); b.end('title')
    b.end('head')
    b.start('body')
    b.start('div',{'class':'container'})
    b.start('header',{'class':'page-header'})
    b.start('h1'); b.data(title); b.end('h1')
    b.end('header')
    img_filename = slugs[name]+'.png'
    b.start('section',{'class':'row'})
    try:
      with open(os.path.join(directory,img_filename),'rb') as f:
        print(re.sub(r'.','',f.read().decode('cp1252','ignore')))
    except FileNotFoundError:
      pass
    else:
      b.start('div',{'class':'col-md-6'})
      b.start('img',{'src':img_filename,'class':'center-block img-responsive'})
      b.end('img')
      b.end('div')
    b.start('div',{'class':'col-md-6'})
    b.start('div',{'class':'panel panel-default'}).append(xml.etree.ElementTree.fromstring(
      '<div class="panel-body">'+markdown.markdown(node.description,output_format="xhtml5")+'</div>'
    ))

    if node.edges:
      #b.start('div',{'class':'col-md-5 col-md-offset-1'})
      b.start('section',{'class':'list-group'})
      for edge in node.edges:
        b.start('a',{'class':'list-group-item','href':rootify(edge.destination)+'.html'})
        b.data(edge.description)
        b.end('a')
      b.end('section')
      #b.end('div')
    b.end('div')
    b.end('div')
    b.end('section')
    b.start('hr'); b.end('hr')
    b.start('footer',{'class':'well'})
    b.start('p',{'class':'pull-right'})
    b.start('a',{'href':'output.gv.cairo.svg'})
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
  #def do_graphviz_with_records():
  #  output_graphviz.append(['node','[shape=record];'])
  #  for name, node in nodes.items():
  #    output_graphviz.append([gv_slug(name),'[label="{{{}}}"];'.format(re.sub(r'"','&quot;',
  #          ''+slugs[name]+' | '+gv_label_escape(textwrap.fill(node[0],50))+'| {'+' | '.join(
  #            '<c{}> {}'.format(i,gv_label_escape(textwrap.fill(v,20))) for i, v in enumerate(node[1].values())
  #          )+'}'
  #        ))
  #      ])
  #  for name, node in nodes.items():
  #    for i, k in enumerate(node[1].keys()):
  #      output_graphviz.append(['{}:c{}'.format(gv_slug(name),i),'->','{}:n'.format(gv_slug(k)),';'])
  #def do_graphviz_with_labels():
  #  output_graphviz.append(['node','[shape=box];'])
  #  for name, node in nodes.items():
  #    output_graphviz.append([gv_slug(name),'[label="{}"];'.format(re.sub(r'"','&quot;',slugs[name]+r'\n'+gv_label_escape(textwrap.fill(node[0],50))))])
  #  for name, node in nodes.items():
  #    for destination, label in node[1].items():
  #      output_graphviz.append([gv_slug(name),'->',gv_slug(destination),'[taillabel="{}"]'.format(re.sub(r'"','&quot;',gv_label_escape(textwrap.fill(label,20))))])
  def do_graphviz_with_nodes():
    output_graphviz.append(['splines=true;'])
    output_graphviz.append(['node','[shape=none];'])
    for name, node in nodes.items():
      output_graphviz.append(['subgraph','cluster_'+gv_slug(name),'{'])
      output_graphviz.append([gv_slug(name),'[label="{}"];'.format(re.sub(r'"','&quot;',slugs[name]+r'\n'+gv_label_escape(textwrap.fill(node.description,50))))])
      for edge in node.edges:
        assert edge.parent == name
        intermediary_node_name = '{}_to_{}'.format(*map(gv_slug,[name,edge.destination]))
        output_graphviz.append([intermediary_node_name,'[label="{}",shape=oval];'.format(re.sub(r'"','&quot;',gv_label_escape(textwrap.fill(edge.description,20))))])
      output_graphviz.append(['}'])
    for name, node in nodes.items():
      for edge in node.edges:
        intermediary_node_name = '{}_to_{}'.format(*map(gv_slug,[name,edge.destination]))
        output_graphviz.append([gv_slug(name),'->',intermediary_node_name])
        output_graphviz.append([intermediary_node_name,'->',gv_slug(edge.destination),'[minlen=3];'])
  do_graphviz_with_nodes()
  output_graphviz.append(['}'])
  filename = os.path.join(directory,'output.gv')
  open(filename,'w').write('\n'.join(' '.join(row) for row in output_graphviz))
  try:
    subprocess.check_call(['dot','-Tsvg:cairo','-O',filename])
  except FileNotFoundError:
    subprocess.check_call([list(glob.glob('graphviz-*/release/bin/dot.exe'))[0],'-Tsvg:cairo','-O',filename])

class UserError(Exception): pass
class NXError(Exception): pass

def compile(filename, output_dir):
  try:
    try:
      rows = list(filter(lambda r: r and any(r),csv.reader(sys.stdin if not filename else open(filename ,newline=''))))
    except FileNotFoundError as e:
      raise UserError(e)
    root = None
    try:
      if rows[0][3].lower().startswith('start'): root = rows[0][4]
    except IndexError:
      pass
    nodes, root = parse_csv(rows[1:],root)
    #print(pformat(nodes))
    write_html(nodes,root,slugify.slugs,output_dir)
    write_graphviz(nodes,slugify.slugs,output_dir)
  except NXError as e:
    pass
  else:
    os.replace(filename,filename+'~')
  finally:
    pass

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

