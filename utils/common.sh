# Send a commit status update to GitHub
# $1    context
# $2    ghstate (pending, success, error, or failure)
# $3    description (optional)
# $4    url (optional)
common_update_github() {

    local context=$1; shift
    local ghstate=$1; shift

    local description=""
    if [ $# -gt 0 ]; then
        description=$1; shift
    fi

    local url=""
    if [ $# -gt 0 ]; then
        url=$1; shift
    fi

    if [ -z "${github_token:-}" ]; then
        echo "No github_token defined, punting on GitHub commit status update:"
        echo $github_repo $github_commit $ghstate "$context" "$description" "$url"
        return
    fi

    $THIS_DIR/utils/ghupdate.py \
        --repo $github_repo \
        --commit $github_commit \
        --token env:github_token \
        --state "$ghstate" \
        --context "$context" \
        --description "$description" \
        --url "$url"

    # Also update the merge sha if we're testing a merge commit.
    # This is useful for homu: https://github.com/servo/homu/pull/54
    if [ -f state/is_merge_sha ]; then
        $THIS_DIR/utils/ghupdate.py \
            --repo $github_repo \
            --commit $(cat state/sha) \
            --token env:github_token \
            --state "$ghstate" \
            --context "$context" \
            --description "$description" \
            --url "$url"
    fi
}
