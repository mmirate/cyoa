cyoa
====

A compiler for static, web-based Choose-Your-Own-Adventures, which uses only the Python 3 standard library. A GUI is launched automatically.

To Install
----------

* Download `cyoa_compiler.py` to anywhere.
* Install [Python](http://www.python.org/download/).
* Download [Graphviz](http://www.graphviz.org/Download..php)
	* Windows users: do not use the MSI. Instead download the zip-file and extract it next to `cyoa_compiler.py`.
	* Mac users: just install the package and it should just work.

To Use
------

* Download the input spreadsheet in CSV format (i.e. from Google Docs).
* Either:
	* Run (often double-click) `cyoa_compiler.py`. A GUI will pop up.
	* (might or might not work for you) Drag the CSV input file onto `cyoa_compiler.py`. A GUI will pop up and the input file's location will be pre-loaded.
* It is reccommended to leave the CSV file in the default download location and let the compiler remove it upon successful compilation. This way, you will remember to re-download the CSV in order to compile with the latest version of the spreadsheet data; the filename will be constant, so just hit "Compile" after re-downloading and it should "Just Work."

Limitations
-----------

* It is not possible to specify formatting in the prose, not even line-breaks. This needs to be fixed, even if only by passing-through raw HTML in the text of the spreadsheet cells.
* Destinations cannot yet be named for their displayed text. This should be a quick fix.
