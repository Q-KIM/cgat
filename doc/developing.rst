=========================
Contributing to CGAT code
=========================

We encourage everyone who uses parts of the CGAT code collection to
contribute. Contributions can take many forms: bugreports, bugfixes,
new scripts and pipelines, documentation, tests, etc. All
contributions are welcome.

Checklist for new scripts/modules
=================================

Before adding a new scripts to the repository, please check if the
following are true:

1. The script performs a non-trivial task. If a one-line command line
   entry using standard unix commands can give the same effect, avoid
   adding a script to the repository.

2. The script has a clear purpose. Scripts should follow the 
   `unix philosophy <http://en.wikipedia.org/wiki/Unix_philosophy>`_.
   They should concentrate on one task and do it well. Ideally,
   the major input and output can be read from and written to standard
   input and standard output, respectively. 

3. The script follows the naming convention of CGAT scripts. 

4. The scripts follows the :ref:`styleguide`.

5. The script implements the ``-h/--help`` options. Ideally, the
   script has been derived :file:`script_template.py`.

6. The script can be imported. Ideally, it imports without performing
   any actions or writing output.

7. The script is well documented and the documentation has been added
   to the CGAT documentation. There should be an entry in
   :file:`doc/scripts.rst` and a file
   :file:`doc/scripts/newscript.py`.

8. The script has at least one test case added to :file:`tests` - and
   the test works.
	
