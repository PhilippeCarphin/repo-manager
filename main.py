import pygit2
import os
from pprint import pprint
from collections.abc import MutableSet

class RepoWrapperError(Exception):
    pass


class RepoWrapper:
    def __init__(self, repo_dir):
        try:
            self._repo = pygit2.Repository(os.path.join(repo_dir, '.git'))
        except pygit2.GitError:
            raise RepoWrapperError()

    def fetch(self, remote="origin"):
        self._repo.remotes[remote].fetch()

    def compare_with_upstream(self, branch_name='master'):
        branch = self._repo.branches[branch_name]
        upstream = branch.upstream
        return self._repo.ahead_behind(branch.target, upstream.target)

    def up_to_date(self):
        for branch in self._repo.branches.local:
            if self.compare_with_upstream(branch) != (0,0):
                return False
        return True

    def branch_info(self, branch_name='master'):
        branch = self._repo.branches[branch_name]
        upstream = branch.upstream
        info_tuple = self._repo.ahead_behind(branch.target, upstream.target)
        print(info_tuple)
        print('{} has {} commits that {} doesn\'t have.'.format(branch.name, info_tuple[0], upstream.name))
        print('{} has {} commits that {} doesn\'t have.'.format(upstream.name, info_tuple[1], branch.name))

    def has_stuff_to_push(self):
        try:
            if self.compare_with_upstream()[0] != 0:
                return True
            mod, new = self.digested_status()
            if mod or new:
                return True

            return False
        except:
            print("Could not get status for repo {}".format(self._repo.workdir))

    def digested_status(self):
        modified = []
        new = []
        for filepath, flags in self._repo.status().items():
            if   flags in [pygit2.GIT_STATUS_WT_MODIFIED, pygit2.GIT_STATUS_INDEX_MODIFIED]:
                modified.append(filepath)
            elif flags in [pygit2.GIT_STATUS_WT_NEW,      pygit2.GIT_STATUS_INDEX_NEW]:
                new.append(filepath)
        return modified, new
    def status(self):
        st = self._repo.status()
        for filepath, flags in self._repo.status().items():
            if flags == pygit2.GIT_STATUS_WT_MODIFIED:
                print("The file {} is modified".format(filepath))
            elif flags == pygit2.GIT_STATUS_IGNORED:
                continue
                print("the file {} is ignored".format(filepath))
            elif flags == pygit2.GIT_STATUS_WT_NEW:
                print("the file {} is new".format(filepath))
            elif flags == pygit2.GIT_STATUS_INDEX_NEW:
                print("the new file {} is in the index".format(filepath))
            elif flags == pygit2.GIT_STATUS_INDEX_MODIFIED:
                print("changes to the file {} are in the index".format(filepath))
            else:
                print("Unhandled flag {} for file {}".format(flags, filepath))
                raise RepoWrapperError()

def get_repos_from_dir(dir):
    realpath = os.path.expanduser(dir)
    repos = []

    for repo in os.listdir(realpath):
        try:
            rw = RepoWrapper(os.path.join(github, repo))
            repos.append(rw)
        except:
            pass

    return repos

class RepoManager(MutableSet):
    def __init__(self):
        self.repos = set()
        # TODO Consider having something to remember about directories
        # maybe one container for directories and their repo list
        # and one other container for individual repos
        # Like github is a directory
        # and ~/.philconfig is a single repo whose parent directory doesn't matter.

    def status(self):
        for repo in self.repos:
            # print("repo = {}".format(repo._repo.workdir))
            if repo.has_stuff_to_push():
                print("Repo {} has stuff to push".format(repo._repo.workdir))

    def add_dir(self, dir):
        realpath = os.path.expanduser(dir)
        for repo in os.listdir(realpath):
            try: self.repos.add(RepoWrapper(os.path.join(github, repo)))
            except RepoWrapperError: pass
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
    repo = RepoWrapper('../flask_test/')
    info = repo._repo.ahead_behind('db7ac576792ecf5041b800ec90c533400e5eae60', 'a9f9007904385781d9c7ab1c6670b0293ca61095')

    github = os.path.expanduser('~/Documents/GitHub')
    repo_list = get_repos_from_dir(github)

    rm = RepoManager()
    rm.add_dir(github)
    rm.add(os.path.expanduser('~/.philconfig'))

    # repo.branch_info('master')
    # repo.status()
    # print(repo.has_stuff_to_push())
    # pprint(repo._repo.status())
    # print(github)
    # print([r._repo.workdir for r in repo_list])

    print(len(repo_list))

    print(len(rm))

    rm.status()