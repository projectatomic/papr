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

    if [ -z "${github_commit:-}" ]; then
        echo "No github_commit defined, ignoring..."
        return
    fi

    if [ -z "${github_token:-}" ]; then
        echo "No github_token defined, punting on GitHub commit status update:"
        echo $github_repo $github_commit $ghstate "$context" "$description" "$url"
        return
    fi

    python3 $THIS_DIR/utils/gh.py \
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
        python3 $THIS_DIR/utils/gh.py \
            --repo $github_repo \
            --commit $(cat state/sha) \
            --token env:github_token \
            --state "$ghstate" \
            --context "$context" \
            --description "$description" \
            --url "$url"
    fi
}

# Block until a node is available through SSH
# $1    node IP address
# $2    private key
ssh_wait() {
    local node_addr=$1; shift
    local node_key=$1; shift

    timeout 120s "$THIS_DIR/utils/sshwait" $node_addr

    # We have to be extra cautious here -- OpenStack
    # networking takes some time to settle, so we wait until
    # we can contact the node for 5 continuous seconds.

    local max_sleep=30
    local failed=1

    sustain_true() {
        local sustain=5
        while [ $sustain -gt 0 ]; do
            if ! ssh -q -n -i $node_key \
                     -o StrictHostKeyChecking=no \
                     -o PasswordAuthentication=no \
                     -o UserKnownHostsFile=/dev/null \
                     root@$node_addr true; then
                        return 1
            fi
            sustain=$((sustain - 1))
            max_sleep=$((max_sleep - 1))
            sleep 1
        done
        failed=0
    }

    while ! sustain_true && [ $max_sleep -gt 0 ]; do
        max_sleep=$((max_sleep - 1))
        sleep 1
    done

    unset -f sustain_true

    if [ $failed == 1 ]; then
        echo "ERROR: Timed out while waiting for SSH."
        return 1
    fi
}
