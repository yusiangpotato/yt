``yt``: a command-line YouTube client
=====================================

NOTE: This is a fork of a old version of yt with the following new features:  

- 1) the default player changed from mplayer to vlc  
- 2) the default codec changed to using 720p MP4 (legacy support in youtube)  
- 3) the ability to use DASH video with the audio automatically fetched*  
- 4) the OMXplayer and mpv maybe not working at all!  
- 5) is working with the v3 API but need the developer key to use  

``yt`` is a command-line front-end to YouTube which allows you to browse YouTube
videos and play them directly from the command-line. It uses ``youtube-dl`` and
``mplayer``, ``omxplayer``, or ``mpv`` to actually *play* the videos.

The combination of a text based interface and ``omxplayer`` makes ``yt`` a great
YouTube client for the Raspberry Pi.

Usage
-----

Launch using ``mplayer`` with::

    yt

or, if you're using a Raspberry Pi, using ``omxplayer``::

    pi-yt

Installation
------------

From GitHub
~~~~~~~~~~~

::

    # Install dependencies
    sudo apt-get install youtube-dl
    # Ensure using latest version of youtube-dl to keep up with YouTube API changes
    sudo youtube-dl -U

    # Install from GitHub
    sudo apt-get install python-setuptools
    git clone https://github.com/yusiangpotato/yt.git
    cd yt
    sudo python setup.py install

                        
Dependencies
------------

Any of

- youtube-dl and mplayer
- youtube-dl and omxplayer
- mpv (which uses libquvi)

Common problems
---------------

Videos don't play when selected in interface
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Make sure you have the latest version of youtube-dl. youtube-dl has a self update
mechanism::

    sudo youtube-dl -U

Omxplayer starts and terminates without playing video
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For high quality videos the default memory allocation on the Raspberry Pi doesn't
provide enough memory to the GPU.

The default 192M ARM, 64M GPU split can be changed to a 128M ARM, 128M GPU split
using raspi-config.

::

    sudo raspi-config
    # Select memory-split
    # Allocate 128M to the GPU
        
See http://elinux.org/RPi_Advanced_Setup for more information.

Getting more help
~~~~~~~~~~~~~~~~~

See https://github.com/rg3/youtube-dl and https://github.com/huceke/omxplayer for
more detailed help.

Contributors
------------

- Rich Wareham
    - Created ``yt``.

- Calum J. Eadie
    - Added OMXPlayer support and pi-yt entry point.

Credits
-------

- `Distribute`_
- `Buildout`_
- `modern-package-template`_
- `youtube-dl`_
- `mplayer`_
- `Omxplayer`_
- Mark Baldridges's `"HOWTO: YouTube on the Raspberry Pi - sans X)"`_

.. _Buildout: http://www.buildout.org/
.. _Distribute: http://pypi.python.org/pypi/distribute
.. _`modern-package-template`: http://pypi.python.org/pypi/modern-package-template
.. _`youtube-dl`: http://rg3.github.com/youtube-dl/
.. _`mplayer`: http://www.mplayerhq.hu/
.. _`Omxplayer`: https://github.com/huceke/omxplayer
.. _`"HOWTO: YouTube on the Raspberry Pi - sans X)"`: http://www.raspberrypi.org/phpBB3/viewtopic.php?p=97710&sid=fa3272a732353dc501cb96d38453b97c#p97710
