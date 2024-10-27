.. role:: python(code)
   :language: python

Frequently Asked Questions
==========================

Welcome to the FAQ section of the project documentation!
This section provides answers to common questions about the Agent Catalog project (key concepts, solutions to
common issues, guidance on using various features, etc...).
For additional information, consult the documentation or community resources.

How do I roll back to a previous catalog version?
-------------------------------------------------

Agent Catalog was built on the principle of agent *snapshots*.
Consequently, it is possible to roll back to a previous catalog version :math:`v` if you have :math:`v`'s version ID.
Some common use cases for rolling back to a previous catalog version include performing A/B testing on different
versions of your agent or rolling back your agent due to some regression.

Catalog versions are Git commit hashes.
To roll back to a previous catalog version, follow these steps:

1. **List Catalog Versions** : Start by running the :command:`agentc status` command with the ``--status-db`` flag to
   list all the published catalog versions of tools in your bucket (here, we are checking in ``travel-sample``):

   .. code-block:: bash

       # run agentc status --help for all options
       agentc status --kind tool --status-db --bucket travel-sample

   Running the command above will return a list of all the tool catalog snapshots you have published to Couchbase.

   .. code-block:: console
       :emphasize-lines: 5, 16

       -----------------------------------------------------------------
       TOOL
       -----------------------------------------------------------------
       db catalog info:
           catalog id: 53010a92d74e96851fb36fc2c69b9c3337140890
                   path            : travel-sample.agent_catalog.tool
                   schema version  : 0.0.0
                   kind of catalog : tool
                   repo version    :
                           time of publish: 2024-10-23 07:16:15.058405+00:00
                           catalog identifier: 53010a92d74e96851fb36fc2c69b9c3337140890
                   embedding model : sentence-transformers/all-MiniLM-L12-v2
                   source dirs     : ['src/resources/agent_c/tools']
                   number of items : 24

           catalog id: fe25a5755bfa9af68e1f1fae9ac45e9e37b37611
                   path            : travel-sample.agent_catalog.tool
                   schema version  : 0.0.0
                   kind of catalog : tool
                   repo version    :
                           time of publish: 2024-10-16 05:34:38.523755+00:00
                           catalog identifier: fe25a5755bfa9af68e1f1fae9ac45e9e37b37611
                   embedding model : sentence-transformers/all-MiniLM-L12-v2
                   source dirs     : ['src/resources/tools']
                   number of items : 2

       -----------------------------------------------------------------

2. **Browse Git Commits**: Next, check the ``catalog id`` from the above output for the Git commit hash at which the
   catalogs were published to the database.
   Open your repository commit history on Github or run the :command:`git log` command in your terminal to view the
   commit history for your project.
   Once you have a comprehensive list of commits, you can decide which catalog version to roll back to.

3. **Perform Rollback**: When you decide which catalog version you want to roll back to, you can move forward
   (or rather, "backward") in three ways:

   a. To revert your changes to a specific commit in a non-destructive manner, run :command:`git revert`.

      .. code-block:: bash

          git revert <commit_hash>..HEAD

      This command will rollback your repository to `<commit_hash>` *but* with a new commit hash.
      This is a safe way to rollback to a previous version without losing your current work, as your existing
      Git commit history will be preserved.

   b. To checkout a particular commit (i.e., all changes associated with some commit), run :command:`git checkout`.

       .. code-block:: bash

           git checkout <commit_hash>

       This command will checkout the commit `<commit_hash>` without creating a new commit.

   c. To revert your changes to a specific commit in a **destructive** manner, run :command:`git reset`.

      .. code-block:: bash

          git reset --hard <commit_hash>

      This command will reset your working Git HEAD to the provided commit if you have not published your changes so
      far.
      **This command is destructive, so make sure all your changes have been committed or are stashed beforehand!**

   For further information on Git, please refer to git documentation
   `here <https://training.github.com/downloads/github-git-cheat-sheet>`_ .
