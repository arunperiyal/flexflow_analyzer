# simulation_functions.sh -- FlexFlow case helpers for the NAS, where flexflow
# itself does not run. Plain BusyBox ash: no bash, no python.
#
#   . ~/simulation_functions.sh      then   sf_help
#
#   show_plt       list the missing binary PLT files of a case
#   show_archive   the othd/oisd parts of a case: steps, range, redundant ones
#   clean_archive  delete othd/oisd parts by number (asks first)
#   clean_plt      delete binary PLT files in a timestep window (asks first)
#
# Every function takes --case DIR (default: the current directory) and
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
    local t1="" t2="" freq="" case_dir="." problem=""
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --t1)      _sf_val "$1" "$#" || return 2; t1=$2; shift ;;
            --t2)      _sf_val "$1" "$#" || return 2; t2=$2; shift ;;
            --freq)    _sf_val "$1" "$#" || return 2; freq=$2; shift ;;
            --case)    _sf_val "$1" "$#" || return 2; case_dir=$2; shift ;;
            --problem) _sf_val "$1" "$#" || return 2; problem=$2; shift ;;
            --t1=*) t1=${1#*=} ;; --t2=*) t2=${1#*=} ;; --freq=*) freq=${1#*=} ;;
            --case=*) case_dir=${1#*=} ;; --problem=*) problem=${1#*=} ;;
            -h|--help)
                echo "Usage: show_plt [--t1 N] [--t2 N] [--freq N] [--case DIR] [--problem NAME]"
                echo "  Lists the missing (and empty) binary PLT files for steps t1..t2, every freq."
                echo "  Defaults: freq = outFreq from simflow.config (else 50), t1 = freq,"
                echo "  t2 = the last PLT present."
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

    echo "Checking $dir/$problem.<step>.plt, steps $t1..$t2 every $freq"
    local t=$t1 expected=0 missing=0 empty=0 f
    while [ "$t" -le "$t2" ]; do
        f="$dir/$problem.$t.plt"
        expected=$((expected + 1))
        if [ ! -e "$f" ]; then
            echo "missing  $f"
            missing=$((missing + 1))
        elif [ ! -s "$f" ]; then
            echo "empty    $f"
            empty=$((empty + 1))
        fi
        t=$((t + freq))
    done

    echo "----------------------------------------"
    if [ $((missing + empty)) -eq 0 ]; then
        echo "All $expected PLT files are present."
        return 0
    fi
    echo "$missing missing, $empty empty, of $expected expected."
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
                echo "  Lists othd_files/ and oisd_files/: size, steps and tsId range of each part,"
                echo "  and which parts are redundant (every step is in another part)."
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

    local type dir rows compiled
    for type in $types; do
        dir="$case_dir/${type}_files"
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
        compiled="$dir/compiled/$problem.$type"
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
                echo "  Deletes parts N1..N2 of othd_files/ and/or oisd_files/ (both without --type),"
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
        dir="$case_dir/${type}_files"
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
# help, and the old names
# ---------------------------------------------------------------------------

sf_help() {
    cat <<'EOF'
FlexFlow case helpers (each takes --case DIR and --problem NAME; -h for details)

  show_plt      [--t1 N] [--t2 N] [--freq N]       missing/empty binary PLT files
  show_archive  [--type othd|oisd]                 othd/oisd parts, ranges, redundant ones
  clean_archive --n N1:N2 [--type othd|oisd]       delete parts (asks; --dry-run)
  clean_plt     --t1 N --t2 N [--freq N]           delete PLT files (asks; --dry-run)

Examples
  show_plt --case CS4SG3U1P0 --t1 4000 --t2 4300 --freq 5
  show_archive --case CS4SG3U1P0
  clean_archive --case CS4SG3U1P0 --type othd --n 2:
  clean_plt --case CS4SG3U1P0 --t1 4005 --t2 4295 --freq 5 --dry-run
EOF
}

check_missing_plt()   { show_plt "$@"; }
clean_archive_files() { clean_archive "$@"; }
