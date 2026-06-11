# Per-package documentation

This repository now has toplevel documentation at nodl.readthedocs.io - but we also want to be previewing/reviewing the per-package documentation as it will appear, so that we are sure to be keeping their concept-level and API documentation clear.

Eventually the per-package documentation, and the toplevel docs (as the `nodl` package), should be built and hosted to docs.ros.org once these are in the ROS buildfarm, assuming we can get the structure we want there.

Come up with a proposal for how our main docs page that currently exists can list an index of the nodl subpackages, linking to their individual documentation.
Those subpackage pages should refer to each other or to the toplevel docs where necessary to not repeat themselves.
These subpackage docs are meant to document the specifics of those packages and their usage.

A consideration: are these separate readthedocs projects/sites or do they get incorporated into the single readthedocs site, with the understanding that on docs.ros.org they'll be a lot more independent? Ideally we don't have to split the implementation very much, and instead just give ourselves the space to see quick and easy PR previews and have an official docs site leading up to official ROS distro release.

Or maybe we just always host our own documentation, and have the docs.ros.org pages link back to them. That could be a fine option.
Either way, we want the rosdoc2-ish docs for every package!

Come up with a proposal for review.
Write all analysis summaries and plans to markdown files on disk in this directory.
Once proposal is accepted, you can implement it.
