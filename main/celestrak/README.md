
The software under this directory has quite a history.

The originals were written in C++ by David Vallado and are now mostly available under the AGPL-3.0 license here: https://github.com/CelesTrak/fundamentals-of-astrodynamics.

Some (the SPG4 routines) are also available in a ZIP file linked to from https://celestrak.org/publications/AIAA/2006-6753/.  On the page https://celestrak.org/publications/AIAA/2006-6753/faq.php the license is given as:

    There is no license associated with the code and you may use it for any purpose—personal or commercial—as you wish. We ask only that you include citations in your documentation and source code to show the source of the code and provide links to the main page, to facilitate communications regarding any questions on the theory or source code. 

Earlier work on SGP4 models can be seen in https://celestrak.org/NORAD/documentation/spacetrk.pdf with FORTRAN routines by Dr T.S. Kelso (https://celestrak.org/webmaster.php).

* https://celestrak.org/brief-history.php
* https://celestrak.org/columns/v04n05/
* https://celestrak.org/publications/AIAA/2006-6753/faq.php

My changes have been only to make the C++ code compile as OpenCl (C) and avoid duplicating some functions.  I have included the AGPL license for where it applies and the original source files for comparison.

