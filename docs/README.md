# Explore Rosetta

## Instructions
- Install rosetta package
- Create tools and/or prompts using the provided [templates](#templates) 
- Run `rosetta --help` to view a complete list of available commands
- Index your tools and create a catalog using the `rosetta index` command - all catalogs will be shown in `./rosetta-catalog` 
- Find catalog items to provide to your agent later using the `rosetta find` command
- After local dev, publish your catalog to Couchbase using the `rosetta publish` command
- Write you agent flow with rosetta
- To enable logs and tracking, make sure to include the auditor; all local logs will appear in `./rosetta-activity` and persistent logs in your Couchbase database
- Test out your application and you're good to go!

For examples of agentic workflow with Rosetta, refer to [rosetta-example](https://github.com/couchbaselabs/rosetta-example) repository.

For a detailed guide, refer to our [pre-beta guide](https://docs.google.com/document/d/1fLjKk31_izPE87AIMQexIwkTqmnHSvdqFvAJ9Xe2N68/edit?usp=sharing).

## Templates

This directory contains the following templates:
- [`tools/`](templates/tools) contains four templates, each outlining the required fields while defining the different types of tools you can create
- [`prompts/`](templates/prompts) contains the template to write prompts