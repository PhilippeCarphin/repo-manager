#!/usr/bin/python3

import pygit2
import os
from collections.abc import MutableSet
import getpass

passwd = getpass.getpass("Please enter password for philippecarphin@github.com")

class CliCredentials(pygit2.RemoteCallbacks):
    def credentials(self, url, username_from_url, allowed_types):
        if allowed_types == pygit2.GIT_CREDTYPE_USERPASS_PLAINTEXT:
            return pygit2.UserPass('philippecarphin', passwd)
        elif allowed_types == pygit2.GITCREDTYPE_USERNAME:
            raise NotImplemented


class RepoWrapperError(Exception):
    pass


class RepoWrapper:
    def __init__(self, repo_dir):
        try:
            self._repo = pygit2.Repository(os.path.join(repo_dir, '.git'))
            self.info = {}
            self.fetch()
            self.refresh()
        except pygit2.GitError:
            raise RepoWrapperError()

    def fetch(self, remote="origin"):
        url=self._repo.remotes[remote].url.lower()
        print("Fetching for {} from url {}".format(self._repo.workdir, url))
        if not url.startswith("https://github.com/philippecarphin"):
            return
        print("      url is from phil's github")
        try:
            self._repo.remotes[remote].fetch(callbacks=CliCredentials())
        except pygit2.GitError:
            print("Error : fetching from remote={} for repo={}".format(remote, self._repo.workdir))

    def branches_with_upstream(self):
        return [b for b in self._repo.branches.local if self._repo.branches[b].upstream is not None]

    def local_branches(self):
        return [b for b in self._repo.branches.local if self._repo.branches[b].upstream is None]

    def refresh(self):
        self.info['remotes'] = {r.name: r.url for r in self._repo.remotes}
        # try:
        #     for r in self.info['remotes']:
        #         self.fetch(r)
        # except pygit2.GitError:
        #     pass
        self.info['tracking-branches'] = {
            b: self.compare_with_upstream(b)
            for b in self.branches_with_upstream()
        }
        self.info['local-only'] = self.local_branches()
        self.info['modified'], self.info['new'], self.info['ignored'] = self.digested_status()
        self.info['clean'] = not (self.info['new'] or self.info['modified'])

    def compare_with_upstream(self, branch_name='master'):
        try:
            branch = self._repo.branches[branch_name]
        except KeyError:
            raise RepoWrapperError(self._repo.name + "has no branch named " + branch_name)
        try:
            upstream = branch.upstream
        except pygit2.GitError:
            raise RepoWrapperError(self._repo.name + ": branch {} has no upstream".format(branch_name))
        return self._repo.ahead_behind(branch.target, upstream.target)

    def up_to_date(self):
        for branch in self._repo.branches.local:
            if self.compare_with_upstream(branch) != (0, 0):
                return False
        return True

    def should_just_push(self):
        try:
            info_tuple = self.info['tracking-branches']['master']
        except KeyError as e:
            print("should_just_push(): KeyError : " + str(e))
            return True
        return self.info['clean'] and info_tuple[1] == 0 and info_tuple[0] != 0

    def should_just_pull(self):
        try:
            info_tuple = self.info['tracking-branches']['master']
        except KeyError as e:
            print("should_just_pull(): KeyError : " + str(e))
            return True
        return self.info['clean'] and info_tuple[0] == 0 and info_tuple[1] != 0

    def workdir_is_clean(self):
        return self.info['clean']

    def digested_status(self):
        """ Returns the modified and untracked files """
        st = self._repo.status().items()
        modified = [filepath for filepath, flags in st if flags in [
                pygit2.GIT_STATUS_WT_MODIFIED,
                pygit2.GIT_STATUS_INDEX_MODIFIED]]
        new = [filepath for filepath, flags in st if flags in [
                pygit2.GIT_STATUS_WT_NEW,
                pygit2.GIT_STATUS_INDEX_NEW]]
        ignored = [filepath for filepath, flags in st if flags in [
                pygit2.GIT_STATUS_IGNORED]]
        return modified, new, ignored


    @property
    def tell_me_what_to_do(self):
        self.refresh()
        if not self.info['clean']:
            return '\033[0;31m'"repo {} has DIRTY work directory \033[0;0m\n".format(self._repo.workdir)
        elif 'master' not in self.info['tracking-branches']:
            # If master has no upstream branch, then as long as it's not dirty,
            # leave it.
            return ''
        elif self.should_just_pull():
            return '\033[0;33m'"repo {} You can FAST FORWARD MERGE \033[0;0m\n".format(self._repo.workdir)
        elif self.should_just_push():
            return '\033[0;33m'"repo {} You can just PUSH \033[0;0m\n".format(self._repo.workdir)
        elif 'master' in self.info['tracking-branches'] and self.info['tracking-branches']['master'] == (0, 0):
            return ''
            # return '\033[0;32m'"repo {} Is clean and up to date".format(self._repo.workdir) + '\033[0;0m'
        else:
            return '\033[0;31m' "repo {} DIVERGED \033[0;0m\n".format(self._repo.workdir)

class RepoContainer:
    def __init__(self, container_dir='.'):
        self.dir = container_dir
        self.repos = []
        self.non_repos = []
        for d in os.listdir(container_dir):
            try:
                repo = RepoWrapper(os.path.join(container_dir, d))
                self.repos.append(repo)
            except RepoWrapperError:
                self.non_repos.append(d)

    def __iter__(self):
        return iter(self.repos)


class RepoManager(MutableSet):
    def __init__(self):
        self.repos = set()
        # TODO Consider having something to remember about directories
        # maybe one container for directories and their repo list
        # and one other container for individual repos
        # Like github is a directory
        # and ~/.philconfig is a single repo whose parent directory doesn't matter.
        self.repo_dirs = set()

    def status(self):
        status = ""
        for repo in self.repos:
            status += repo.tell_me_what_to_do

        for repo_dir in self.repo_dirs:
            for repo in repo_dir:
                try:
                    status += repo.tell_me_what_to_do
                except:
                    pass
            non_repo_string = '\n'.join(repo_dir.non_repos)
            status += non_repo_string
        return status

    def fetch(self):
        for repo in self.repos:
            repo.fetch()
        for repo_dir in self.repo_dirs:
            for repo in repo_dir:
                repo.fetch()

    def add_dir(self, repo_dir):
        realpath = os.path.expanduser(repo_dir)
        self.repo_dirs.add(RepoContainer(realpath))

    # TODO : Warn user of non-repos contained in directory

    def report(self):
        # TODO Say which repos have stuff to push
        # TODO Warn if there are non-git-repos in the directory

        pass

    def add(self, repo_dir):
        self.repos.add(RepoWrapper(repo_dir))

    def discard(self, repo):
        self.repos.discard(repo)

    def __contains__(self, element):
        return element in self.repos

    def __iter__(self):
        return iter(self.repos)

    def __len__(self):
        return len(self.repos)


if __name__ == "__main__":
    github = os.path.expanduser('~/Documents/GitHub')
    rm = RepoManager()
    rm.add_dir(github)
    rm.add(os.path.expanduser('~/.philconfig'))

    # rm.fetch()
    import time
    while True :
        statu = rm.status()
        os.system('cls' if os.name == 'nt' else 'clear')
        print(statu)
        if statu == "":
            print("everything's good!")
            break
        time.sleep(10)

    # TODO If there are non-git-repos in a directory, inform user
    # TODO Do this for all remotes, or maybe configurable
    # TODO For all branches, compare_inf9 = (!0, !0), inform user
    # TODO If working directory is dirty, inform user
    # TODO For all branches, compare_info = (0, !=0), do merge
    # TODO For all branches, compare_info = (!= 0, 0), do_push
    # TODO Add priorities: for philconfig and tests for example.
