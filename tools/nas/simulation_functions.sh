# simulation_functions.sh -- FlexFlow case helpers for the NAS, where flexflow
# itself does not run. Plain BusyBox ash: no bash, no python.
#
#   . ~/simulation_functions.sh      then   sf_help
#
#   show_plt       list the missing binary PLT files of a case (and, with
#                  --since, the ones made before the last restart)
#   show_archive   the othd/oisd parts of a case: steps, range, redundant ones
#   clean_archive  delete othd/oisd parts by number (asks first)
#   clean_plt      delete binary PLT files in a timestep window (asks first)
#   missing        the gaps in any numbered series of files (slice_{}.png, ...)
#
# The case functions take --case DIR (default: the current directory) and
# --problem NAME (default: `problem` in the case's simflow.config, else riser).
# Options may be written --t1 50 or --t1=50; -h shows a function's usage.

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_sf_err() { echo "Error: $*" >&2; }

# _sf_val OPTION ARGC: an option that takes a value has one after it
_sf_val() {
    [ "$2" -ge 2 ] && return 0
    _sf_err "$1 needs a value"
    return 1
}

# _sf_int NAME VALUE: VALUE is a whole number
_sf_int() {
    case "$2" in
        ''|*[!0-9]*) _sf_err "$1 needs a whole number, got '$2'"; return 1 ;;
    esac
}

# _sf_config DIR KEY: KEY's value in DIR/simflow.config (empty if unset)
_sf_config() {
    [ -f "$1/simflow.config" ] || return 0
    awk -v k="$2" '
        { sub(/#.*/, "") }
        index($0, "=") {
            key = $0; sub(/=.*/, "", key); gsub(/[ \t\r]/, "", key)
            if (key == k) { v = $0; sub(/^[^=]*=/, "", v); gsub(/[ \t\r]/, "", v); print v; exit }
        }' "$1/simflow.config"
}

# _sf_cfgdir DIR: where the case's simflow.config is (DIR, or DIR/.. inside binary/)
_sf_cfgdir() {
    if [ -f "$1/simflow.config" ]; then echo "$1"
    elif [ -f "$1/../simflow.config" ]; then echo "$1/.."
    else echo "$1"
    fi
}

_sf_size() {
    awk -v b="$1" 'BEGIN {
        split("B KB MB GB TB", u); i = 1
        while (b >= 1024 && i < 5) { b /= 1024; i++ }
        if (i == 1) printf "%d B", b; else printf "%.1f %s", b, u[i] }'
}

# _sf_confirm QUESTION: y/N
_sf_confirm() {
    printf "%s (y/N): " "$1"
    read -r _sf_answer
    case "$_sf_answer" in [yY]|[yY][eE][sS]) return 0 ;; esac
    return 1
}

# _sf_plt_steps DIR PROBLEM: the steps of DIR/PROBLEM.<step>.plt, sorted
_sf_plt_steps() {
    ls "$1" 2>/dev/null | sed -n "s/^$2\.\([0-9][0-9]*\)\.plt\$/\1/p" | sort -n
}

# _sf_plt_dir CASE: CASE/binary, or CASE itself when run inside binary/
_sf_plt_dir() {
    if [ -d "$1/binary" ]; then echo "$1/binary"; else echo "$1"; fi
}

# ---------------------------------------------------------------------------
# show_plt
# ---------------------------------------------------------------------------

show_plt() {
    local t1="" t2="" freq="" case_dir="." problem="" since="" restart=""
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --since)   _sf_val "$1" "$#" || return 2; since=$2; shift ;;
            --restart) _sf_val "$1" "$#" || return 2; restart=$2; shift ;;
            --since=*) since=${1#*=} ;; --restart=*) restart=${1#*=} ;;
            --t1)      _sf_val "$1" "$#" || return 2; t1=$2; shift ;;
            --t2)      _sf_val "$1" "$#" || return 2; t2=$2; shift ;;
            --freq)    _sf_val "$1" "$#" || return 2; freq=$2; shift ;;
            --case)    _sf_val "$1" "$#" || return 2; case_dir=$2; shift ;;
            --problem) _sf_val "$1" "$#" || return 2; problem=$2; shift ;;
            --t1=*) t1=${1#*=} ;; --t2=*) t2=${1#*=} ;; --freq=*) freq=${1#*=} ;;
            --case=*) case_dir=${1#*=} ;; --problem=*) problem=${1#*=} ;;
            -h|--help)
                echo "Usage: show_plt [--t1 N] [--t2 N] [--freq N] [--case DIR] [--problem NAME]"
                echo "                [--since DATE] [--restart N]"
                echo "  Lists the missing (and empty) binary PLT files for steps t1..t2, every freq."
                echo "  Defaults: freq = outFreq from simflow.config (else 50), t1 = freq,"
                echo "  t2 = the last PLT present."
                echo "  --since DATE  when the resumed job started ('2026-10-20 14:00', or @EPOCH):"
                echo "                a PLT past the restart step that reached the NAS before then"
                echo "                is listed as stale -- it came from the run before the restart,"
                echo "                whose steps past it were computed again. A file sent late"
                echo "                can slip through; a new one is never called stale."
                echo "  --restart N   the restart step (default: restartTsId in simflow.config)"
                return 0 ;;
            *) _sf_err "show_plt: unknown option '$1' (show_plt -h)"; return 2 ;;
        esac
        shift
    done

    [ -d "$case_dir" ] || { _sf_err "no such case directory: $case_dir"; return 1; }
    local cfg dir
    cfg=$(_sf_cfgdir "$case_dir")
    dir=$(_sf_plt_dir "$case_dir")
    [ -n "$problem" ] || problem=$(_sf_config "$cfg" problem)
    [ -n "$problem" ] || problem=riser
    [ -n "$freq" ] || freq=$(_sf_config "$cfg" outFreq)
    [ -n "$freq" ] || freq=50
    [ -n "$t1" ] || t1=$freq
    if [ -z "$t2" ]; then
        t2=$(_sf_plt_steps "$dir" "$problem" | tail -n 1)
        [ -n "$t2" ] || { _sf_err "no $problem.*.plt in $dir: give --t2"; return 1; }
    fi
    _sf_int --t1 "$t1" && _sf_int --t2 "$t2" && _sf_int --freq "$freq" || return 2
    [ "$freq" -gt 0 ] || { _sf_err "--freq must be above 0"; return 2; }
    [ "$t1" -le "$t2" ] || { _sf_err "--t1 ($t1) is after --t2 ($t2)"; return 2; }

    # The restart: restartTsId counts only while restartFlag is on, the way
    # the resume writes them
    if [ -z "$restart" ]; then
        case "$(_sf_config "$cfg" restartFlag)" in ''|0) ;;
            *) restart=$(_sf_config "$cfg" restartTsId) ;; esac
    fi
    [ -z "$restart" ] || _sf_int --restart "$restart" || return 2
    local since_s=""
    if [ -n "$since" ]; then
        [ -n "$restart" ] || { _sf_err "--since: no restart in $cfg/simflow.config (restartFlag/restartTsId); give --restart N"; return 2; }
        since_s=$(date -d "$since" +%s 2>/dev/null) \
            || { _sf_err "--since: not a date: '$since' (e.g. '2026-10-20 14:00')"; return 2; }
    fi

    echo "Checking $dir/$problem.<step>.plt, steps $t1..$t2 every $freq"
    [ -z "$since_s" ] || echo "Stale: steps past $restart that arrived before $(date -d "@$since_s" '+%Y-%m-%d %H:%M')"
    local t=$t1 expected=0 missing=0 empty=0 stale=0 f
    while [ "$t" -le "$t2" ]; do
        f="$dir/$problem.$t.plt"
        expected=$((expected + 1))
        if [ ! -e "$f" ]; then
            echo "missing  $f"
            missing=$((missing + 1))
        elif [ ! -s "$f" ]; then
            echo "empty    $f"
            empty=$((empty + 1))
        elif [ -n "$since_s" ] && [ "$t" -gt "$restart" ] && [ "$(stat -c %Y "$f")" -lt "$since_s" ]; then
            echo "stale    $f"
            stale=$((stale + 1))
        fi
        t=$((t + freq))
    done

    echo "----------------------------------------"
    if [ $((missing + empty + stale)) -eq 0 ]; then
        echo "All $expected PLT files are present."
        if [ -n "$since_s" ]; then
            echo "None past the restart at $restart arrived before the resumed job started."
        elif [ -n "$restart" ]; then
            echo "Restarted at $restart: add --since DATE (when the resumed job started) to find"
            echo "PLT files made before it."
        fi
        return 0
    fi
    if [ -n "$since_s" ]; then
        echo "$missing missing, $empty empty, $stale stale, of $expected expected."
        [ "$stale" -eq 0 ] || echo "Stale files are from the run before the restart at $restart: make them again from the resumed run."
    else
        echo "$missing missing, $empty empty, of $expected expected."
        [ -z "$restart" ] || echo "Restarted at $restart: add --since DATE to find PLT files made before it."
    fi
    return 1
}

# ---------------------------------------------------------------------------
# show_archive
# ---------------------------------------------------------------------------

# _sf_parts DIR PROBLEM TYPE: the part numbers N of DIR/PROBLEM<N>.TYPE, sorted
_sf_parts() {
    ls "$1" 2>/dev/null | sed -n "s/^$2\([0-9][0-9]*\)\.$3\$/\1/p" | sort -n
}

# _sf_scan FILE: "steps first last" from the file's tsId lines
_sf_scan() {
    grep '^tsId' "$1" 2>/dev/null | awk '
        NR == 1 { lo = hi = $2 + 0 }
        { v = $2 + 0; if (v < lo) lo = v; if (v > hi) hi = v }
        END { if (NR) print NR, lo, hi; else print 0, "-", "-" }'
}

# _sf_archive_rows DIR PROBLEM TYPE: one line per part, "n steps first last bytes note"
#   note: inside:K  every step of it is in part K too (safe to delete)
#         restart   starts at or before a step an earlier part already has
#         gap       steps are missing between it and the earlier parts
# _sf_parts_dir CASE TYPE: where the parts are, archive/ or (older cases) TYPE_files/
_sf_parts_dir() {
    if [ -d "$1/${2}_files/archive" ]; then echo "$1/${2}_files/archive"
    else echo "$1/${2}_files"; fi
}

_sf_archive_rows() {
    local n f
    for n in $(_sf_parts "$1" "$2" "$3"); do
        f="$1/$2$n.$3"
        echo "$n $(_sf_scan "$f") $(stat -c %s "$f")"
    done | awk '
        { n[NR] = $1; s[NR] = $2; lo[NR] = $3; hi[NR] = $4; b[NR] = $5 }
        END {
            seen = -1
            for (i = 1; i <= NR; i++) {
                note = ""
                if (s[i] == 0) note = "no-steps"
                for (j = 1; j <= NR && note == ""; j++) {
                    if (j == i || s[j] == 0) continue
                    if (lo[j] <= lo[i] && hi[i] <= hi[j] && (s[j] > s[i] || (s[j] == s[i] && j < i)))
                        note = "inside:" n[j]
                }
                if (note == "" && seen >= 0) {
                    if (lo[i] <= seen) note = "restart"
                    else if (lo[i] > seen + 1) note = "gap"
                }
                if (s[i] > 0 && hi[i] > seen) seen = hi[i]
                print n[i], s[i], lo[i], hi[i], b[i], (note == "" ? "-" : note)
            }
        }'
}

# _sf_show_rows PROBLEM TYPE < rows
_sf_show_rows() {
    local n steps lo hi bytes note
    printf "  %-16s %10s %8s %8s %8s  %s\n" file size steps first last note
    while read -r n steps lo hi bytes note; do
        case "$note" in
            inside:*) note="redundant: inside $1${note#inside:}.$2" ;;
            restart)  note="restart (overlaps earlier parts)" ;;
            gap)      note="GAP before it" ;;
            no-steps) note="NO tsId found" ;;
            -)        note="" ;;
        esac
        printf "  %-16s %10s %8s %8s %8s  %s\n" "$1$n.$2" "$(_sf_size "$bytes")" \
            "$steps" "$lo" "$hi" "$note"
    done
}

show_archive() {
    local case_dir="." problem="" types="othd oisd"
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --case)    _sf_val "$1" "$#" || return 2; case_dir=$2; shift ;;
            --problem) _sf_val "$1" "$#" || return 2; problem=$2; shift ;;
            --type)    _sf_val "$1" "$#" || return 2; types=$2; shift ;;
            --case=*) case_dir=${1#*=} ;; --problem=*) problem=${1#*=} ;; --type=*) types=${1#*=} ;;
            -h|--help)
                echo "Usage: show_archive [--case DIR] [--problem NAME] [--type othd|oisd]"
                echo "  Lists the parts in othd_files/archive/ and oisd_files/archive/ (or directly in"
                echo "  othd_files/ for a case from before archive/): size, steps and tsId range of"
                echo "  each part, and which are redundant (every step is in another part)."
                return 0 ;;
            *) _sf_err "show_archive: unknown option '$1' (show_archive -h)"; return 2 ;;
        esac
        shift
    done
    case "$types" in othd|oisd|"othd oisd") ;;
        *) _sf_err "--type must be othd or oisd"; return 2 ;; esac
    [ -d "$case_dir" ] || { _sf_err "no such case directory: $case_dir"; return 1; }
    [ -n "$problem" ] || problem=$(_sf_config "$case_dir" problem)
    [ -n "$problem" ] || problem=riser

    local type dir rows compiled cleaned
    for type in $types; do
        dir=$(_sf_parts_dir "$case_dir" "$type")
        echo "== $dir"
        if [ ! -d "$dir" ]; then echo "  (no such directory)"; continue; fi
        echo "  scanning..."
        rows=$(_sf_archive_rows "$dir" "$problem" "$type")
        if [ -z "$rows" ]; then
            echo "  no $problem<N>.$type parts"
        else
            echo "$rows" | _sf_show_rows "$problem" "$type"
            echo "$rows" | awk -v p="$problem" -v t="$type" '
                $2 > 0 { if (lo == "" || $3 < lo) lo = $3; if ($4 > hi) hi = $4 }
                $6 ~ /^inside:/ { r++ }
                END { printf "  %d part(s), tsId %s..%s", NR, lo, hi
                      if (r) printf ", %d redundant (clean_archive --type %s --n ...)", r, t
                      print "" }'
        fi
        cleaned=$(_sf_parts "$case_dir/${type}_files/cleaned" "$problem" "$type" | wc -w)
        [ "$cleaned" -gt 0 ] && echo "  cleaned: $cleaned run(s) in $case_dir/${type}_files/cleaned"
        compiled="$case_dir/${type}_files/$problem.$type"
        [ -f "$compiled" ] && echo "  compiled: $compiled  ($(_sf_size "$(stat -c %s "$compiled")"))"
    done
    return 0
}

# ---------------------------------------------------------------------------
# clean_archive
# ---------------------------------------------------------------------------

clean_archive() {
    local case_dir="." problem="" types="othd oisd" range="" n1="" n2="" dry=0
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --type)    _sf_val "$1" "$#" || return 2; types=$2; shift ;;
            --n)       _sf_val "$1" "$#" || return 2; range=$2; shift ;;
            --n1)      _sf_val "$1" "$#" || return 2; n1=$2; shift ;;
            --n2)      _sf_val "$1" "$#" || return 2; n2=$2; shift ;;
            --case)    _sf_val "$1" "$#" || return 2; case_dir=$2; shift ;;
            --problem) _sf_val "$1" "$#" || return 2; problem=$2; shift ;;
            --type=*) types=${1#*=} ;; --n=*) range=${1#*=} ;;
            --case=*) case_dir=${1#*=} ;; --problem=*) problem=${1#*=} ;;
            --dry-run) dry=1 ;;
            -h|--help)
                echo "Usage: clean_archive --n N1:N2 [--type othd|oisd] [--case DIR] [--problem NAME] [--dry-run]"
                echo "  Deletes parts N1..N2 of othd_files/archive/ and/or oisd_files/archive/ (both"
                echo "  without --type; directly in othd_files/ for a case from before archive/),"
                echo "  after showing them and asking. --n takes N, N1:N2, N1: (to the last) or :N2."
                echo "  Warns about any part that is not redundant (it holds steps no other part has)."
                return 0 ;;
            *) _sf_err "clean_archive: unknown option '$1' (clean_archive -h)"; return 2 ;;
        esac
        shift
    done
    case "$types" in othd|oisd|"othd oisd") ;;
        *) _sf_err "--type must be othd or oisd"; return 2 ;; esac
    # --n1/--n2 are the old clean_archive_files spelling
    if [ -z "$range" ] && [ -n "$n1$n2" ]; then range="${n1:-1}:$n2"; fi
    [ -n "$range" ] || { _sf_err "which parts? --n N, N1:N2, N1: or :N2 (clean_archive -h)"; return 2; }
    case "$range" in
        *:*) n1=${range%%:*}; n2=${range#*:} ;;
        *)   n1=$range; n2=$range ;;
    esac
    [ -n "$n1" ] || n1=1
    _sf_int "--n start" "$n1" || return 2
    [ -z "$n2" ] || _sf_int "--n end" "$n2" || return 2
    [ -d "$case_dir" ] || { _sf_err "no such case directory: $case_dir"; return 1; }
    [ -n "$problem" ] || problem=$(_sf_config "$case_dir" problem)
    [ -n "$problem" ] || problem=riser

    local type dir rows picked files="" count=0 bytes=0 risky=0
    for type in $types; do
        dir=$(_sf_parts_dir "$case_dir" "$type")
        [ -d "$dir" ] || continue
        echo "== $dir  (scanning...)"
        rows=$(_sf_archive_rows "$dir" "$problem" "$type")
        [ -n "$rows" ] || { echo "  no parts"; continue; }
        picked=$(echo "$rows" | awk -v a="$n1" -v b="$n2" '$1 >= a+0 && (b == "" || $1 <= b+0)')
        if [ -z "$picked" ]; then echo "  no parts numbered $n1..${n2:-last}"; continue; fi
        echo "$picked" | _sf_show_rows "$problem" "$type"
        if [ "$(echo "$picked" | wc -l)" -eq "$(echo "$rows" | wc -l)" ]; then
            echo "  WARNING: these are ALL the $type parts: nothing of $type would be left."
            risky=1
        fi
        local n s lo hi b note
        while read -r n s lo hi b note; do
            case "$note" in
                inside:*) ;;
                *) echo "  WARNING: $problem$n.$type is not redundant: its steps $lo..$hi are lost."
                   risky=1 ;;
            esac
            files="$files $dir/$problem$n.$type"
            count=$((count + 1))
            bytes=$((bytes + b))
        done <<EOF
$picked
EOF
    done

    echo "----------------------------------------"
    [ "$count" -gt 0 ] || { echo "Nothing to delete."; return 0; }
    echo "$count file(s), $(_sf_size "$bytes")."
    if [ "$dry" -eq 1 ]; then echo "Dry run: nothing deleted."; return 0; fi
    if [ "$risky" -eq 1 ]; then
        printf "Data would be lost. Type DELETE to go on: "
        read -r _sf_answer
        [ "$_sf_answer" = DELETE ] || { echo "Cancelled."; return 0; }
    else
        _sf_confirm "Delete them?" || { echo "Cancelled."; return 0; }
    fi
    local f status=0
    for f in $files; do
        if rm -f "$f"; then echo "removed  $f"; else status=1; fi
    done
    return $status
}

# ---------------------------------------------------------------------------
# clean_plt
# ---------------------------------------------------------------------------

clean_plt() {
    local t1="" t2="" freq="" case_dir="." problem="" dry=0
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --t1)      _sf_val "$1" "$#" || return 2; t1=$2; shift ;;
            --t2)      _sf_val "$1" "$#" || return 2; t2=$2; shift ;;
            --freq)    _sf_val "$1" "$#" || return 2; freq=$2; shift ;;
            --case)    _sf_val "$1" "$#" || return 2; case_dir=$2; shift ;;
            --problem) _sf_val "$1" "$#" || return 2; problem=$2; shift ;;
            --t1=*) t1=${1#*=} ;; --t2=*) t2=${1#*=} ;; --freq=*) freq=${1#*=} ;;
            --case=*) case_dir=${1#*=} ;; --problem=*) problem=${1#*=} ;;
            --dry-run) dry=1 ;;
            -h|--help)
                echo "Usage: clean_plt --t1 N --t2 N [--freq N] [--case DIR] [--problem NAME] [--dry-run]"
                echo "  Deletes the binary PLT files for steps t1..t2, after showing them and asking."
                echo "  With --freq, only steps t1, t1+freq, t1+2*freq, ... ; without, every step."
                return 0 ;;
            *) _sf_err "clean_plt: unknown option '$1' (clean_plt -h)"; return 2 ;;
        esac
        shift
    done
    [ -n "$t1" ] && [ -n "$t2" ] || { _sf_err "clean_plt needs --t1 and --t2 (clean_plt -h)"; return 2; }
    _sf_int --t1 "$t1" && _sf_int --t2 "$t2" || return 2
    [ -z "$freq" ] || _sf_int --freq "$freq" || return 2
    [ -z "$freq" ] || [ "$freq" -gt 0 ] || { _sf_err "--freq must be above 0"; return 2; }
    [ "$t1" -le "$t2" ] || { _sf_err "--t1 ($t1) is after --t2 ($t2)"; return 2; }
    [ -d "$case_dir" ] || { _sf_err "no such case directory: $case_dir"; return 1; }
    local cfg dir
    cfg=$(_sf_cfgdir "$case_dir")
    dir=$(_sf_plt_dir "$case_dir")
    [ -n "$problem" ] || problem=$(_sf_config "$cfg" problem)
    [ -n "$problem" ] || problem=riser

    local steps
    steps=$(_sf_plt_steps "$dir" "$problem" | awk -v a="$t1" -v b="$t2" -v f="$freq" '
        $1 >= a+0 && $1 <= b+0 && (f == "" || ($1 - a) % f == 0)')
    local which="every step"
    [ -z "$freq" ] || which="every $freq"
    if [ -z "$steps" ]; then
        echo "No $problem.<step>.plt in $dir for steps $t1..$t2 ($which)."
        return 0
    fi

    local count bytes=0 s first last
    count=$(echo "$steps" | wc -l)
    first=$(echo "$steps" | head -n 1)
    last=$(echo "$steps" | tail -n 1)
    for s in $steps; do bytes=$((bytes + $(stat -c %s "$dir/$problem.$s.plt"))); done
    echo "In $dir, steps $t1..$t2 ($which):"
    if [ "$count" -le 10 ]; then
        for s in $steps; do echo "  $problem.$s.plt"; done
    else
        echo "$steps" | head -n 3 | sed "s/.*/  $problem.&.plt/"
        echo "  ... ($((count - 6)) more)"
        echo "$steps" | tail -n 3 | sed "s/.*/  $problem.&.plt/"
    fi
    echo "----------------------------------------"
    echo "$count file(s), $(_sf_size "$bytes"), steps $first..$last."
    if [ "$dry" -eq 1 ]; then echo "Dry run: nothing deleted."; return 0; fi
    _sf_confirm "Delete them?" || { echo "Cancelled."; return 0; }
    local status=0
    for s in $steps; do rm -f "$dir/$problem.$s.plt" || status=1; done
    echo "Removed $count file(s)."
    return $status
}

# ---------------------------------------------------------------------------
# missing
# ---------------------------------------------------------------------------

# _sf_listing DIR EMPTY: "F name" per file in DIR ("E name" for a 0-byte one
# when EMPTY is 1); hidden files and directories are left out
_sf_listing() {
    local f
    for f in "$1"/*; do
        [ -f "$f" ] || continue
        if [ "$2" -eq 1 ] && [ ! -s "$f" ]; then echo "E ${f##*/}"; else echo "F ${f##*/}"; fi
    done
}

# _sf_series < listing: "prefix<TAB>suffix" of each numbered series. Names
# with the same text between their digit runs are one shape; the run with the
# most values is the number, so riser.{}_0.out and riser.{}_1.out are two
# series (one per subgrid). A series needs two numbers or more.
_sf_series() {
    awk '
        {
            s = substr($0, 3); k = 0; key = ""
            while (match(s, /[0-9]+/)) {
                k++; txt[k] = substr(s, 1, RSTART - 1); run[k] = substr(s, RSTART, RLENGTH)
                key = key txt[k] "\034"; s = substr(s, RSTART + RLENGTH)
            }
            if (!k) next
            key = key s
            if (!(key in nf)) { nk[key] = k; tail[key] = s; for (i = 1; i <= k; i++) text[key, i] = txt[i] }
            c = ++nf[key]; runs = run[1]
            for (i = 2; i <= k; i++) runs = runs "\034" run[i]
            file[key, c] = runs
            for (i = 1; i <= k; i++)
                if (!((key, i, run[i]) in seen)) { seen[key, i, run[i]] = 1; distinct[key, i]++ }
        }
        END {
            for (key in nf) {
                k = nk[key]; vary = 1
                for (i = 2; i <= k; i++) if (distinct[key, i] >= distinct[key, vary]) vary = i
                for (c = 1; c <= nf[key]; c++) {
                    split(file[key, c], r, "\034"); pre = ""; suf = ""
                    for (i = 1; i <= k; i++) {
                        if (i < vary) pre = pre text[key, i] r[i]
                        else if (i == vary) pre = pre text[key, i]
                        else suf = suf text[key, i] r[i]
                    }
                    suf = suf tail[key]; g = pre "\t" suf
                    if (!((g, r[vary]) in val)) { val[g, r[vary]] = 1; nval[g]++ }
                }
            }
            for (g in nval) if (nval[g] >= 2) print g
        }' | sort
}

# _sf_check SHOWN PREFIX SUFFIX T1 T2 FREQ FLAGS LABEL < listing: report one
# series. SHOWN goes before each name; FLAGS holds e(mpty) x(tra) q(uiet)
# p(ipe: names only); LABEL puts the pattern on the summary line.
_sf_check() {
    awk -v at="$1" -v pre="$2" -v suf="$3" -v t1="$4" -v t2="$5" -v freq="$6" \
        -v flags="$7" -v label="$8" '
        function gcd(a, b) { while (b) { t = a % b; a = b; b = t } return a }
        {
            kind = substr($0, 1, 1); name = substr($0, 3)
            lp = length(pre); ls = length(suf); mid = length(name) - lp - ls
            if (mid < 1 || substr(name, 1, lp) != pre || substr(name, lp + mid + 1) != suf) next
            d = substr(name, lp + 1, mid)
            if (d ~ /[^0-9]/) next
            n = d + 0; found[n] = 1; if (kind == "E") empty[n] = 1
            if (length(d) > 1 && d ~ /^0/) pad = length(d)
            if (lo == "" || n < lo) lo = n; if (hi == "" || n > hi) hi = n
        }
        END {
            pattern = at pre "{}" suf
            a = (t1 != "") ? t1 + 0 : lo; b = (t2 != "") ? t2 + 0 : hi
            if (a == "" || b == "") {
                printf "missing: no file matches %s (give --t1 and --t2 to list them all)\n", pattern > "/dev/stderr"
                exit 1
            }
            if (a > b) { printf "Error: --t1 %d is after the last step, %d\n", a, b > "/dev/stderr"; exit 2 }
            f = freq + 0; guessed = (freq == "")
            if (guessed) { f = 0; for (n in found) if (n >= a && n <= b) f = gcd(f, n - a); if (!f) f = 1 }
            if ((b - a) / f > 5000000) { printf "Error: %d..%d every %d is too many steps; give --freq\n", a, b, f > "/dev/stderr"; exit 2 }
            if (index(flags, "x")) {
                for (n in found) if (n >= a && n <= b && (n - a) % f) xs[++nx] = n + 0
                for (i = 2; i <= nx; i++) { v = xs[i]; for (j = i - 1; j >= 1 && xs[j] > v; j--) xs[j + 1] = xs[j]; xs[j + 1] = v }
            }
            kinds = index(flags, "e") || index(flags, "x"); quiet = index(flags, "q"); pipe = index(flags, "p")
            fmt = "%s%s" (pad ? "%0" pad "d" : "%d") "%s\n"; x = 1
            for (t = a; t <= b; t += f) {
                while (x <= nx && xs[x] < t) { row("extra", xs[x]); x++ }
                expected++
                if (!(t in found)) { missing++; row("missing", t) }
                else if (index(flags, "e") && (t in empty)) { empties++; row("empty", t) }
            }
            while (x <= nx) { row("extra", xs[x]); x++ }
            if (!pipe || quiet) {
                text = missing ? sprintf("%d of %d missing", missing, expected) : sprintf("all %d present", expected)
                if (index(flags, "e")) text = text sprintf(", %d empty", empties)
                if (index(flags, "x")) text = text sprintf(", %d extra", nx)
                text = text sprintf("; %d..%d every %d", a, b, f) (guessed ? " (inferred)" : "")
                if (label) text = pattern ": " text
                if (shown && !quiet) print ""
                print ((missing || empties) ? "x " : "ok ") text
            }
            exit (missing || empties) ? 1 : 0
        }
        function row(k, n) {
            if (quiet) return
            shown = 1
            if (pipe && !kinds) printf fmt, at, pre, n, suf
            else printf "%-8s " fmt, k, at, pre, n, suf
        }'
}

missing() {
    local t1="" t2="" freq="" flags="" args="" n=0 a b
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --t1)   _sf_val "$1" "$#" || return 2; t1=$2; shift ;;
            --t2)   _sf_val "$1" "$#" || return 2; t2=$2; shift ;;
            --freq) _sf_val "$1" "$#" || return 2; freq=$2; shift ;;
            --t1=*) t1=${1#*=} ;; --t2=*) t2=${1#*=} ;; --freq=*) freq=${1#*=} ;;
            --empty) flags="${flags}e" ;;
            --extra) flags="${flags}x" ;;
            -q)      flags="${flags}q" ;;
            -h|--help)
                echo "Usage: missing [dir] [pattern] [--t1 N] [--t2 N] [--freq N] [--empty] [--extra] [-q]"
                echo "  The numbers of a series like slice_xVor_{}.png that have no file; {} is"
                echo "  the number. Without a pattern, every numbered series in dir (default: here):"
                echo "  names that differ only in a number, so riser.{}_0.out, riser.{}_1.out, ..."
                echo "  one per subgrid. The directory can also be part of the pattern."
                echo "  --t1/--t2  first/last number (default: the lowest/highest found)"
                echo "  --freq N   step (default: inferred from the files)"
                echo "  --empty    also report 0-byte files;  --extra  files between the steps"
                echo "  -q         only the summary line"
                echo "  Zero padding follows the files. Exits 1 if any is missing (or empty)."
                echo "  In a pipe it prints just the names:  missing post | wc -l"
                echo "  Examples:  missing post"
                echo "             missing post 'slice_xVor_{}.png' --t1 3000 --t2 5000 --freq 50"
                echo "             missing binary 'riser.{}.plt' --empty"
                return 0 ;;
            -?*) _sf_err "missing: unknown option '$1' (missing -h)"; return 2 ;;
            *) n=$((n + 1)); [ "$n" -eq 1 ] && a=$1 || b=$1 ;;
        esac
        shift
    done
    [ "$n" -le 2 ] || { _sf_err "missing: too many arguments (missing -h)"; return 2; }
    [ -z "$t1" ] || _sf_int --t1 "$t1" || return 2
    [ -z "$t2" ] || _sf_int --t2 "$t2" || return 2
    [ -z "$freq" ] || _sf_int --freq "$freq" || return 2
    [ -z "$freq" ] || [ "$freq" -gt 0 ] || { _sf_err "--freq must be 1 or more"; return 2; }
    if [ -n "$t1" ] && [ -n "$t2" ] && [ "$t1" -gt "$t2" ]; then
        _sf_err "--t1 ($t1) is after --t2 ($t2)"; return 2
    fi
    [ -t 1 ] || flags="${flags}p"
    local empty=0
    case "$flags" in *e*) empty=1 ;; esac

    local dir pattern=""
    case "$n" in
        0) dir=. ;;
        1) if [ -d "$a" ]; then dir=$a; else pattern=$a; dir=""; fi ;;
        2) dir=$a; pattern=$b ;;
    esac
    if [ -n "$pattern" ]; then
        case "$pattern" in */*)
            [ -z "$dir" ] && dir=${pattern%/*} || dir="${dir%/}/${pattern%/*}"
            pattern=${pattern##*/} ;; esac
        case "$pattern" in
            *"{}"*"{}"*|"") _sf_err "missing: the file name needs one {} where the number goes"; return 2 ;;
            *"{}"*) ;;
            *) _sf_err "missing: the file name needs one {} where the number goes (or give just a directory)"; return 2 ;;
        esac
    fi
    [ -n "$dir" ] || dir=.
    [ -d "$dir" ] || { _sf_err "missing: not a directory: $dir"; return 1; }
    local at="${dir%/}/"
    [ "$dir" = . ] && at=""
    [ "$dir" = / ] && at=/

    local listing status=0 rc tab
    listing=$(_sf_listing "$dir" "$empty")
    if [ -n "$pattern" ]; then
        echo "$listing" | _sf_check "$at" "${pattern%%"{}"*}" "${pattern#*"{}"}" "$t1" "$t2" "$freq" "$flags" ""
        return $?
    fi
    tab=$(printf '\t')
    local series pre suf first=1
    series=$(echo "$listing" | _sf_series)
    [ -n "$series" ] || { echo "missing: no numbered series in $dir" >&2; return 1; }
    while IFS=$tab read -r pre suf; do
        case "$flags" in *[qp]*) ;; *) [ "$first" -eq 1 ] || echo ;; esac
        first=0
        echo "$listing" | _sf_check "$at" "$pre" "$suf" "$t1" "$t2" "$freq" "$flags" 1
        rc=$?
        [ "$rc" -le "$status" ] || status=$rc
    done <<EOF
$series
EOF
    return $status
}

# ---------------------------------------------------------------------------
# help, and the old names
# ---------------------------------------------------------------------------

sf_help() {
    cat <<'EOF'
FlexFlow case helpers (the case ones take --case DIR and --problem NAME; -h for details)

  show_plt      [--t1 N] [--t2 N] [--freq N]       missing/empty binary PLT files
                [--since DATE]                     ... and stale ones from before a restart
  show_archive  [--type othd|oisd]                 othd/oisd parts, ranges, redundant ones
  clean_archive --n N1:N2 [--type othd|oisd]       delete parts (asks; --dry-run)
  clean_plt     --t1 N --t2 N [--freq N]           delete PLT files (asks; --dry-run)
  missing       [dir] [pattern] [--freq N]         gaps in a numbered series (no --case)

Examples
  show_plt --case CS4SG3U1P0 --t1 4000 --t2 4300 --freq 5
  show_plt --case CS4SG3U1P0 --since '2026-10-20 14:00'
  show_archive --case CS4SG3U1P0
  clean_archive --case CS4SG3U1P0 --type othd --n 2:
  clean_plt --case CS4SG3U1P0 --t1 4005 --t2 4295 --freq 5 --dry-run
  missing CS4SG3U1P0/post                     # every series in post/
  missing CS4SG3U1P0/post 'slice_xVor_{}.png' --freq 50
EOF
}

check_missing_plt()   { show_plt "$@"; }
clean_archive_files() { clean_archive "$@"; }
