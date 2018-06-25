#!/usr/local/bin/python3.7

import pygit2
import os
from collections.abc import MutableSet


class RepoWrapperError(Exception):
    pass


class RepoWrapper:
    def __init__(self, repo_dir):
        try:
            self._repo = pygit2.Repository(os.path.join(repo_dir, '.git'))
            self.info = {}
            self.refresh()
        except pygit2.GitError:
            raise RepoWrapperError()

    def fetch(self, remote="origin"):
        self._repo.remotes[remote].fetch()

    def branches_with_upstream(self):
        return [b for b in self._repo.branches.local if self._repo.branches[b].upstream is not None]

    def local_branches(self):
        return [b for b in self._repo.branches.local if self._repo.branches[b].upstream is None]

    def refresh(self):
        self.info['remotes'] = {r.name: r.url for r in self._repo.remotes}
        try:
            for r in self.info['remotes']:
                self.fetch(r)
        except pygit2.GitError:
            pass
        self.info['branch'] = {
            b: self.compare_with_upstream(b)
            for b in self.branches_with_upstream()
        }
        self.info['local-only'] = self.local_branches()
        self.info['modified'], self.info['new'] = self.digested_status()
        self.info['clean'] = not (self.info['new'] or self.info['modified'])

    def compare_with_upstream(self, branch_name='master'):
        branch = None
        try:
            branch = self._repo.branches[branch_name]
        except KeyError:
            print(self._repo.name + "has no branch named " + branch_name)
        try:
            upstream = branch.upstream
        except pygit2.GitError:
            print(self._repo.name + ": branch {} has no upstream".format(branch_name))
            return
        return self._repo.ahead_behind(branch.target, upstream.target)

    def up_to_date(self):
        for branch in self._repo.branches.local:
            if self.compare_with_upstream(branch) != (0, 0):
                return False
        return True

    def branch_info(self, branch_name='master'):
        try:
            branch = self._repo.branches[branch_name]
        except KeyError:
            print(self._repo.name + "has no branch named " + branch_name)
            return
        upstream = branch.upstream
        info_tuple = self._repo.ahead_behind(branch.target, upstream.target)
        print(info_tuple)
        print('{} has {} commits that {} doesn\'t have.'.format(branch.name, info_tuple[0], upstream.name))
        print('{} has {} commits that {} doesn\'t have.'.format(upstream.name, info_tuple[1], branch.name))

    def should_just_push(self):
        try:
            info_tuple = self.info['branch']['master']
        except KeyError:
            print(self._repo.workdir + "has no branch named " + 'master')
            return True
        return self.info['clean'] and info_tuple[1] == 0 and info_tuple[0] != 0

    def should_just_pull(self):

        try:
            info_tuple = self.info['branch']['master']
        except KeyError:
            print(self._repo.workdir + "has no branch named " + 'master')
            return True
        return self.info['clean'] and info_tuple[0] == 0 and info_tuple[1] != 0

    def workdir_is_clean(self):
        return self.info['clean']

    def has_stuff_to_push(self):
        try:
            if self.compare_with_upstream()[0] != 0:
                return True
            mod, new = self.digested_status()
            if mod or new:
                return True

            return False
        except RepoWrapperError:
            print("Could not get status for repo {}".format(self._repo.workdir))

    def digested_status(self):
        st = self._repo.status().items()
        modified = [
            filepath
            for filepath, flags in st if flags in [
                pygit2.GIT_STATUS_WT_MODIFIED,
                pygit2.GIT_STATUS_INDEX_MODIFIED
            ]

        ]
        new = [
            filepath
            for filepath, flags in st if flags in [
                pygit2.GIT_STATUS_WT_NEW,
                pygit2.GIT_STATUS_INDEX_NEW
            ]

        ]
        return modified, new

    def status(self):
        st = self._repo.status()
        for filepath, flags in st.items():
            if flags == pygit2.GIT_STATUS_WT_MODIFIED:
                print("The file {} is modified".format(filepath))
            elif flags == pygit2.GIT_STATUS_IGNORED:
                continue
                # print("the file {} is ignored".format(filepath))
            elif flags == pygit2.GIT_STATUS_WT_NEW:
                print("the file {} is new".format(filepath))
            elif flags == pygit2.GIT_STATUS_INDEX_NEW:
                print("the new file {} is in the index".format(filepath))
            elif flags == pygit2.GIT_STATUS_INDEX_MODIFIED:
                print("changes to the file {} are in the index".format(filepath))
            else:
                print("Unhandled flag {} for file {}".format(flags, filepath))
                raise RepoWrapperError()

    def tell_me_what_to_do(self):
        if not self.info['clean']:
            print('\033[0;31m'"repo {} has DIRTY work directory".format(self._repo.workdir) + '\033[0;0m')
        elif self.should_just_pull():
            print('\033[0;33m'"repo {} You can FAST FORWARD MERGE".format(self._repo.workdir) + '\033[0;0m')
        elif self.should_just_push():
            print('\033[0;33m'"repo {} You can just PUSH".format(self._repo.workdir) + '\033[0;0m')
        elif 'master' in self.info['branch'] and self.info['branch']['master'] == (0, 0):
            pass
            # print('\033[0;32m'"repo {} Is clean and up to date".format(self._repo.workdir) + '\033[0;0m')
        else:
            print('\033[0;31m' "repo {} DIVERGED".format(self._repo.workdir) + '\033[0;0m')


def get_repos_from_dir(repo_dir):
    realpath = os.path.expanduser(repo_dir)
    repos = []

    for repo in os.listdir(realpath):
        try:
            rw = RepoWrapper(os.path.join(github, repo))
            repos.append(rw)
        except RepoWrapperError:
            pass

    return repos


number = 0


class RepoDir:
    def __init__(self, repo_dir='.'):
        self.dir = repo_dir
        self.repos = []
        self.non_repos = []
        for d in os.listdir(repo_dir):
            try:
                repo = RepoWrapper(os.path.join(repo_dir, d))
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
        for repo in self.repos:
            repo.tell_me_what_to_do()

        for repo_dir in self.repo_dirs:
            for repo in repo_dir:
                repo.tell_me_what_to_do()

    def add_dir(self, repo_dir):
        realpath = os.path.expanduser(repo_dir)
        self.repo_dirs.add(RepoDir(realpath))

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
    # repo = RepoWrapper('../flask_test/')
    # info = repo._repo.ahead_behind('db7ac576792ecf5041b800ec90c533400e5eae60',
    # 'a9f9007904385781d9c7ab1c6670b0293ca61095')

    github = os.path.expanduser('~/Documents/GitHub')
    # repo_list = get_repos_from_dir(github)

    # rm = RepoManager()
    # rm.add_dir(github)
    # rm.add(os.path.expanduser('~/.philconfig'))

    # repo.branch_info('master')
    # repo.status()
    # print(repo.has_stuff_to_push())
    # pprint(repo._repo.status())
    # print(github)
    # print([r._repo.workdir for r in repo_list])

    # print(len(repo_list))

    # print(len(rm))

    # rm.status()
    # rm.status()
    # pprint(repo.stats)
    # for b, info_tuple in repo.stats['branch'].items():
    #    print("{}:{}".format(b, info_tuple))
    # print(number)



    # TODO If there are non-git-repos in a directory, inform user
    # TODO Do this for all remotes, or maybe configurable
    # TODO For all branches, compare_inf9 = (!0, !0), inform user
    # TODO If working directory is dirty, inform user
    # TODO For all branches, compare_info = (0, !=0), do merge
    # TODO For all branches, compare_info = (!= 0, 0), do_push
