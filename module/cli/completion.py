"""
Shell completion generator for FlexFlow CLI
"""

import os
import sys
from pathlib import Path


BASH_COMPLETION_SCRIPT = '''# Bash completion for flexflow CLI
# Source this file or add to ~/.bashrc

_flexflow_completions() {
    local cur prev words cword
    _init_completion || return

    # Get the command (if any)
    local cmd=""
    local i
    for (( i=1; i < cword; i++ )); do
        if [[ "${words[i]}" != -* ]]; then
            cmd="${words[i]}"
            break
        fi
    done

    # Top-level commands and flags
    local commands="info new preview statistics plot compare template tecplot docs case data field config"
    local global_flags="--install --uninstall --update --completion --examples --version --help -h"

    # If no command yet, complete commands and global flags
    if [[ -z "$cmd" ]]; then
        COMPREPLY=( $(compgen -W "$commands $global_flags" -- "$cur") )
        return
    fi

    # Command-specific completions
    case "$cmd" in
        case)
            # Parse for subcommand (show or create)
            local subcommand=""
            for (( i=2; i < cword; i++ )); do
                if [[ "${words[i]}" == "show" ]] || [[ "${words[i]}" == "create" ]]; then
                    subcommand="${words[i]}"
                    break
                fi
            done
            
            if [[ -z "$subcommand" ]]; then
                # No subcommand yet
                local flags="-v --verbose -h --help --examples"
                COMPREPLY=( $(compgen -W "show create $flags" -- "$cur") )
            else
                # Have subcommand
                case "$subcommand" in
                    show)
                        local flags="-v --verbose -h --help --examples"
                        if [[ "$cur" == -* ]]; then
                            COMPREPLY=( $(compgen -W "$flags" -- "$cur") )
                        else
                            _flexflow_complete_cases
                        fi
                        ;;
                    create)
                        local flags="--ref-case --problem-name --np --freq --from-config --force --list-vars --dry-run -v --verbose -h --help --examples"
                        if [[ "$cur" == -* ]]; then
                            COMPREPLY=( $(compgen -W "$flags" -- "$cur") )
                        else
                            case "$prev" in
                                --ref-case)
                                    _filedir -d
                                    ;;
                                --from-config)
                                    _filedir
                                    ;;
                                *)
                                    # No default completion for case name
                                    ;;
                            esac
                        fi
                        ;;
                esac
            fi
            ;;
        data)
            # Parse for subcommand (show or stats)
            local subcommand=""
            for (( i=2; i < cword; i++ )); do
                if [[ "${words[i]}" == "show" ]] || [[ "${words[i]}" == "stats" ]]; then
                    subcommand="${words[i]}"
                    break
                fi
            done
            
            if [[ -z "$subcommand" ]]; then
                # No subcommand yet
                local flags="-v --verbose -h --help --examples"
                COMPREPLY=( $(compgen -W "show stats $flags" -- "$cur") )
            else
                # Have subcommand
                case "$subcommand" in
                    show)
                        local flags="--node --component --start-time --end-time --start-step --end-step -v --verbose -h --help --examples"
                        if [[ "$cur" == -* ]]; then
                            COMPREPLY=( $(compgen -W "$flags" -- "$cur") )
                        else
                            case "$prev" in
                                --component)
                                    COMPREPLY=( $(compgen -W "x y z magnitude" -- "$cur") )
                                    ;;
                                --node|--start-time|--end-time|--start-step|--end-step)
                                    ;;
                                *)
                                    _flexflow_complete_cases
                                    ;;
                            esac
                        fi
                        ;;
                    stats)
                        local flags="--node --component -v --verbose -h --help --examples"
                        if [[ "$cur" == -* ]]; then
                            COMPREPLY=( $(compgen -W "$flags" -- "$cur") )
                        else
                            case "$prev" in
                                --component)
                                    COMPREPLY=( $(compgen -W "x y z magnitude" -- "$cur") )
                                    ;;
                                --node)
                                    ;;
                                *)
                                    _flexflow_complete_cases
                                    ;;
                            esac
                        fi
                        ;;
                esac
            fi
            ;;
        field)
            # Parse for subcommand (info or extract)
            local subcommand=""
            for (( i=2; i < cword; i++ )); do
                if [[ "${words[i]}" == "info" ]] || [[ "${words[i]}" == "extract" ]]; then
                    subcommand="${words[i]}"
                    break
                fi
            done
            
            if [[ -z "$subcommand" ]]; then
                # No subcommand yet
                local flags="-v --verbose -h --help --examples"
                COMPREPLY=( $(compgen -W "info extract $flags" -- "$cur") )
            else
                # Delegate to tecplot completion (same functionality)
                case "$subcommand" in
                    info)
                        local flags="--basic --variables --zones --checks --stats --detailed --sample-file -v --verbose -h --help --examples"
                        if [[ "$cur" == -* ]]; then
                            COMPREPLY=( $(compgen -W "$flags" -- "$cur") )
                        else
                            _flexflow_complete_cases
                        fi
                        ;;
                    extract)
                        local flags="--variables --zone --timestep --output-file --xmin --xmax --ymin --ymax --zmin --zmax -v --verbose -h --help --examples"
                        if [[ "$cur" == -* ]]; then
                            COMPREPLY=( $(compgen -W "$flags" -- "$cur") )
                        else
                            case "$prev" in
                                --output-file)
                                    _filedir
                                    ;;
                                *)
                                    _flexflow_complete_cases
                                    ;;
                            esac
                        fi
                        ;;
                esac
            fi
            ;;
        config)
            # Parse for subcommand (template)
            local subcommand=""
            for (( i=2; i < cword; i++ )); do
                if [[ "${words[i]}" == "template" ]]; then
                    subcommand="${words[i]}"
                    break
                fi
            done
            
            if [[ -z "$subcommand" ]]; then
                # No subcommand yet
                local flags="-v --verbose -h --help --examples"
                COMPREPLY=( $(compgen -W "template $flags" -- "$cur") )
            else
                # template subcommand
                local flags="--output --force -v --verbose -h --help --examples"
                if [[ "$cur" == -* ]]; then
                    COMPREPLY=( $(compgen -W "$flags" -- "$cur") )
                else
                    case "$prev" in
                        --output)
                            _filedir
                            ;;
                        template)
                            COMPREPLY=( $(compgen -W "single multi fft" -- "$cur") )
                            ;;
                        *)
                            if [[ -z "${words[3]}" ]] || [[ "${words[3]}" == -* ]]; then
                                COMPREPLY=( $(compgen -W "single multi fft" -- "$cur") )
                            fi
                            ;;
                    esac
                fi
            fi
            ;;
        info)
            local flags="-v --verbose -h --help --examples"
            if [[ "$cur" == -* ]]; then
                COMPREPLY=( $(compgen -W "$flags" -- "$cur") )
            else
                _flexflow_complete_cases
            fi
            ;;
        new)
            local flags="--ref-case --problem-name --np --freq --from-config --force --list-vars --dry-run -v --verbose -h --help --examples"
            if [[ "$cur" == -* ]]; then
                COMPREPLY=( $(compgen -W "$flags" -- "$cur") )
            else
                case "$prev" in
                    --ref-case)
                        _filedir -d
                        ;;
                    --from-config)
                        _filedir
                        ;;
                    --problem-name|--np|--freq)
                        # No completion for text/numeric values
                        ;;
                    *)
                        # No default completion for case name
                        ;;
                esac
            fi
            ;;
        preview)
            local flags="--node --start-time --end-time -v --verbose -h --help --examples"
            if [[ "$cur" == -* ]]; then
                COMPREPLY=( $(compgen -W "$flags" -- "$cur") )
            else
                case "$prev" in
                    --node|--start-time|--end-time)
                        # No completion for numeric values
                        ;;
                    *)
                        _flexflow_complete_cases
                        ;;
                esac
            fi
            ;;
        statistics)
            local flags="--node -v --verbose -h --help --examples"
            if [[ "$cur" == -* ]]; then
                COMPREPLY=( $(compgen -W "$flags" -- "$cur") )
            else
                case "$prev" in
                    --node)
                        # No completion for numeric values
                        ;;
                    *)
                        _flexflow_complete_cases
                        ;;
                esac
            fi
            ;;
        plot)
            local flags="--node --data-type --component --plot-type --traj-x --traj-y --traj-z \\
                        --start-time --end-time --start-step --end-step --plot-style \\
                        --title --xlabel --ylabel --legend --legend-style --fontsize --fontname \\
                        --output --no-display --input-file -v --verbose -h --help --examples"
            if [[ "$cur" == -* ]]; then
                COMPREPLY=( $(compgen -W "$flags" -- "$cur") )
            else
                case "$prev" in
                    --data-type)
                        COMPREPLY=( $(compgen -W "displacement force moment pressure" -- "$cur") )
                        ;;
                    --component|--traj-x|--traj-y|--traj-z)
                        COMPREPLY=( $(compgen -W "x y z magnitude tx ty tz all" -- "$cur") )
                        ;;
                    --plot-type)
                        COMPREPLY=( $(compgen -W "time fft traj2d traj3d" -- "$cur") )
                        ;;
                    --input-file|--output)
                        _filedir
                        ;;
                    --node|--start-time|--end-time|--start-step|--end-step|--fontsize| \\
                    --plot-style|--title|--xlabel|--ylabel|--legend|--legend-style|--fontname)
                        # No completion for these
                        ;;
                    *)
                        _flexflow_complete_cases
                        ;;
                esac
            fi
            ;;
        compare)
            local flags="--node --data-type --component --plot-type \\
                        --start-time --end-time --start-step --end-step \\
                        --title --xlabel --ylabel --legend --legend-style \\
                        --fontsize --fontname --plot-style --output --no-display \\
                        --subplot --input-file -v --verbose -h --help --examples"
            if [[ "$cur" == -* ]]; then
                COMPREPLY=( $(compgen -W "$flags" -- "$cur") )
            else
                case "$prev" in
                    --data-type)
                        COMPREPLY=( $(compgen -W "displacement force moment pressure" -- "$cur") )
                        ;;
                    --component)
                        COMPREPLY=( $(compgen -W "x y z magnitude tx ty tz all" -- "$cur") )
                        ;;
                    --plot-type)
                        COMPREPLY=( $(compgen -W "time fft traj2d traj3d" -- "$cur") )
                        ;;
                    --input-file|--output)
                        _filedir
                        ;;
                    --node|--start-time|--end-time|--start-step|--end-step| \\
                    --fontsize|--fontname|--plot-style|--title|--xlabel|--ylabel| \\
                    --legend|--legend-style|--subplot)
                        # No completion for these
                        ;;
                    *)
                        _flexflow_complete_cases
                        ;;
                esac
            fi
            ;;
        template)
            local flags="--output --force -v --verbose -h --help --examples"
            if [[ "$cur" == -* ]]; then
                COMPREPLY=( $(compgen -W "$flags" -- "$cur") )
            else
                case "$prev" in
                    --output)
                        _filedir
                        ;;
                    template)
                        COMPREPLY=( $(compgen -W "single multi fft" -- "$cur") )
                        ;;
                    *)
                        if [[ -z "${words[2]}" ]] || [[ "${words[2]}" == -* ]]; then
                            COMPREPLY=( $(compgen -W "single multi fft" -- "$cur") )
                        fi
                        ;;
                esac
            fi
            ;;
        docs)
            local flags="-h --help"
            if [[ "$cur" == -* ]]; then
                COMPREPLY=( $(compgen -W "$flags" -- "$cur") )
            else
                COMPREPLY=( $(compgen -W "main plot compare info template statistics preview tecplot" -- "$cur") )
            fi
            ;;
                tecplot)
                    local subcommand_args case_args
                    
                    # Parse for subcommand (info or extract)
                    subcommand_args=()
                    case_args=()
                    local has_subcommand=0
                    
                    for word in "${words[@]:2}"; do
                        if [[ "$word" == "info" ]] || [[ "$word" == "extract" ]]; then
                            has_subcommand=1
                            break
                        fi
                    done
                    
                    if [[ $has_subcommand -eq 0 ]]; then
                        # No subcommand yet, offer subcommands and global flags
                        local flags="-v --verbose -h --help --examples"
                        COMPREPLY=( $(compgen -W "info extract $flags" -- "$cur") )
                    else
                        # Have subcommand, delegate to subcommand completion
                        case "${words[2]}" in
                            info)
                                local flags="--basic --variables --zones --checks --stats \\
                                            --detailed --sample-file -v --verbose -h --help"
                                if [[ "$cur" == -* ]]; then
                                    COMPREPLY=( $(compgen -W "$flags" -- "$cur") )
                                else
                                    case "$prev" in
                                        --sample-file)
                                            # No completion for numeric values
                                            ;;
                                        *)
                                            _flexflow_complete_cases
                                            ;;
                                    esac
                                fi
                                ;;
                            extract)
                                local flags="--variables --zone --timestep --output-file \\
                                            --xmin --xmax --ymin --ymax --zmin --zmax \\
                                            -v --verbose -h --help"
                                if [[ "$cur" == -* ]]; then
                                    COMPREPLY=( $(compgen -W "$flags" -- "$cur") )
                                else
                                    case "$prev" in
                                        --variables|--zone|--timestep|--xmin|--xmax|--ymin|--ymax|--zmin|--zmax)
                                            # No completion for these
                                            ;;
                                        --output-file)
                                            _filedir
                                            ;;
                                        *)
                                            _flexflow_complete_cases
                                            ;;
                                    esac
                                fi
                                ;;
                        esac
                    fi
                    ;;
    esac
}

# Helper function to complete case directories
_flexflow_complete_cases() {
    local IFS=$'\\n'
    # Look for directories matching CS* or *U* patterns
    local cases=()
    for dir in CS* *U*/; do
        if [[ -d "$dir" ]]; then
            cases+=("${dir%/}")
        fi
    done 2>/dev/null
    COMPREPLY=( $(compgen -W "${cases[*]}" -- "$cur") )
}

complete -F _flexflow_completions flexflow
'''

ZSH_COMPLETION_SCRIPT = '''#compdef flexflow
# Zsh completion for flexflow CLI

_flexflow() {
    local -a commands global_flags
    commands=(
        'info:Show case information'
        'new:Create a new case directory from reference template'
        'preview:Preview displacement data in table format'
        'statistics:Show statistical analysis of data'
        'plot:Create plots from a single case'
        'compare:Compare multiple cases on a single plot'
        'template:Generate YAML configuration templates'
        'tecplot:Inspect and work with Tecplot PLT files'
        'docs:View documentation'
    )
    
    global_flags=(
        '--install[Install flexflow command globally]'
        '--uninstall[Uninstall flexflow command]'
        '--update[Update flexflow installation]'
        '--version[Show version information]'
        '(-h --help)'{-h,--help}'[Show help message]'
    )

    _arguments -C \\
        "1: :{_describe 'command' commands}" \\
        '*:: :->args' \\
        $global_flags

    case $state in
        args)
            case $words[1] in
                info)
                    _arguments \\
                        '1:case:_flexflow_cases' \\
                        '(-v --verbose)'{-v,--verbose}'[Enable verbose output]' \\
                        '(-h --help)'{-h,--help}'[Show help]' \\
                        '--examples[Show usage examples]'
                    ;;
                new)
                    _arguments \\
                        '1:case_name:' \\
                        '--ref-case[Reference case directory]:directory:_directories' \\
                        '--problem-name[Problem name]:name:' \\
                        '--np[Number of processors]:processors:' \\
                        '--freq[Output frequency]:frequency:' \\
                        '--from-config[Load from YAML file]:file:_files' \\
                        '--force[Overwrite existing directory]' \\
                        '--list-vars[List available variables]' \\
                        '--dry-run[Preview without creating files]' \\
                        '(-v --verbose)'{-v,--verbose}'[Enable verbose output]' \\
                        '(-h --help)'{-h,--help}'[Show help]' \\
                        '--examples[Show usage examples]'
                    ;;
                preview)
                    _arguments \\
                        '1:case:_flexflow_cases' \\
                        '--node[Node ID to preview]:node:' \\
                        '--start-time[Start time for preview]:time:' \\
                        '--end-time[End time for preview]:time:' \\
                        '(-v --verbose)'{-v,--verbose}'[Enable verbose output]' \\
                        '(-h --help)'{-h,--help}'[Show help]' \\
                        '--examples[Show usage examples]'
                    ;;
                statistics)
                    _arguments \\
                        '1:case:_flexflow_cases' \\
                        '--node[Node ID to analyze]:node:' \\
                        '(-v --verbose)'{-v,--verbose}'[Enable verbose output]' \\
                        '(-h --help)'{-h,--help}'[Show help]' \\
                        '--examples[Show usage examples]'
                    ;;
                plot)
                    _arguments \\
                        '1:case:_flexflow_cases' \\
                        '--node[Node ID to plot]:node:' \\
                        '--data-type[Data type]:type:(displacement force moment pressure)' \\
                        '--component[Component to plot]:component:(x y z magnitude tx ty tz all)' \\
                        '--plot-type[Plot type]:type:(time fft traj2d traj3d)' \\
                        '--traj-x[X component for trajectory]:component:(x y z magnitude)' \\
                        '--traj-y[Y component for trajectory]:component:(x y z magnitude)' \\
                        '--traj-z[Z component for trajectory]:component:(x y z magnitude)' \\
                        '--start-time[Start time]:time:' \\
                        '--end-time[End time]:time:' \\
                        '--start-step[Start timestep]:step:' \\
                        '--end-step[End timestep]:step:' \\
                        '--plot-style[Plot style]:style:' \\
                        '--title[Plot title]:title:' \\
                        '--xlabel[X-axis label]:label:' \\
                        '--ylabel[Y-axis label]:label:' \\
                        '--legend[Legend label]:label:' \\
                        '--legend-style[Legend style]:style:' \\
                        '--fontsize[Font size]:size:' \\
                        '--fontname[Font name]:name:' \\
                        '--output[Output file]:file:_files' \\
                        '--no-display[Do not display plot]' \\
                        '--input-file[Load config from YAML]:file:_files -g "*.yaml"' \\
                        '(-v --verbose)'{-v,--verbose}'[Enable verbose output]' \\
                        '(-h --help)'{-h,--help}'[Show help]' \\
                        '--examples[Show usage examples]'
                    ;;
                compare)
                    _arguments \\
                        '*:case:_flexflow_cases' \\
                        '--node[Node ID to plot]:node:' \\
                        '--data-type[Data type]:type:(displacement force moment pressure)' \\
                        '--component[Component to plot]:component:(x y z magnitude tx ty tz all)' \\
                        '--plot-type[Plot type]:type:(time fft traj2d traj3d)' \\
                        '--start-time[Start time]:time:' \\
                        '--end-time[End time]:time:' \\
                        '--start-step[Start timestep]:step:' \\
                        '--end-step[End timestep]:step:' \\
                        '--title[Plot title]:title:' \\
                        '--xlabel[X-axis label]:label:' \\
                        '--ylabel[Y-axis label]:label:' \\
                        '--legend[Legend labels]:labels:' \\
                        '--legend-style[Legend style]:style:' \\
                        '--fontsize[Font size]:size:' \\
                        '--fontname[Font name]:name:' \\
                        '--plot-style[Plot styles]:styles:' \\
                        '--output[Output file]:file:_files' \\
                        '--no-display[Do not display plot]' \\
                        '--subplot[Subplot layout]:layout:' \\
                        '--input-file[Load config from YAML]:file:_files -g "*.yaml"' \\
                        '(-v --verbose)'{-v,--verbose}'[Enable verbose output]' \\
                        '(-h --help)'{-h,--help}'[Show help]' \\
                        '--examples[Show usage examples]'
                    ;;
                template)
                    _arguments \\
                        '1:type:(single multi fft)' \\
                        '--output[Output file]:file:_files' \\
                        '--force[Overwrite existing file]' \\
                        '(-v --verbose)'{-v,--verbose}'[Enable verbose output]' \\
                        '(-h --help)'{-h,--help}'[Show help]' \\
                        '--examples[Show usage examples]'
                    ;;
                docs)
                    _arguments \\
                        '1:topic:(main plot compare info template statistics preview tecplot)' \\
                        '(-h --help)'{-h,--help}'[Show help]'
                    ;;
                tecplot)
                    _arguments -C \\
                        '1:subcommand:(info extract)' \\
                        '*:: :->tecplot_args'
                    
                    case $state in
                        tecplot_args)
                            case $words[1] in
                                info)
                                    _arguments \\
                                        '1:case:_flexflow_cases' \\
                                        '--basic[Show only basic information]' \\
                                        '--variables[Show variable names]' \\
                                        '--zones[Show zone information]' \\
                                        '--checks[Show consistency checks]' \\
                                        '--stats[Show statistics]' \\
                                        '--detailed[Show detailed statistics]' \\
                                        '--sample-file[Analyze specific timestep]:step:' \\
                                        '(-v --verbose)'{-v,--verbose}'[Enable verbose output]' \\
                                        '(-h --help)'{-h,--help}'[Show help]'
                                    ;;
                                extract)
                                    _arguments \\
                                        '1:case:_flexflow_cases' \\
                                        '--variables[Variables to extract]:variables:' \\
                                        '--zone[Zone name]:zone:' \\
                                        '--timestep[Timestep to extract]:step:' \\
                                        '--output-file[Output file]:file:_files' \\
                                        '--xmin[Minimum X coordinate]:xmin:' \\
                                        '--xmax[Maximum X coordinate]:xmax:' \\
                                        '--ymin[Minimum Y coordinate]:ymin:' \\
                                        '--ymax[Maximum Y coordinate]:ymax:' \\
                                        '--zmin[Minimum Z coordinate]:zmin:' \\
                                        '--zmax[Maximum Z coordinate]:zmax:' \\
                                        '(-v --verbose)'{-v,--verbose}'[Enable verbose output]' \\
                                        '(-h --help)'{-h,--help}'[Show help]'
                                    ;;
                            esac
                            ;;
                    esac
                    ;;
            esac
            ;;
    esac
}

# Helper function to complete case directories
_flexflow_cases() {
    local -a cases
    cases=(${(f)"$(ls -d CS* *U*/ 2>/dev/null | sed 's#/##')"})
    _describe 'case directory' cases
}

_flexflow "$@"
'''

FISH_COMPLETION_SCRIPT = '''# Fish completion for flexflow CLI

# Global options
complete -c flexflow -l install -d "Install flexflow command globally"
complete -c flexflow -l uninstall -d "Uninstall flexflow command"
complete -c flexflow -l update -d "Update flexflow installation"
complete -c flexflow -l version -d "Show version information"
complete -c flexflow -s h -l help -d "Show help message"

# Commands
complete -c flexflow -f -n "__fish_use_subcommand" -a "info" -d "Show case information"
complete -c flexflow -f -n "__fish_use_subcommand" -a "new" -d "Create a new case directory"
complete -c flexflow -f -n "__fish_use_subcommand" -a "preview" -d "Preview displacement data"
complete -c flexflow -f -n "__fish_use_subcommand" -a "statistics" -d "Show statistical analysis"
complete -c flexflow -f -n "__fish_use_subcommand" -a "plot" -d "Create plots from a single case"
complete -c flexflow -f -n "__fish_use_subcommand" -a "compare" -d "Compare multiple cases"
complete -c flexflow -f -n "__fish_use_subcommand" -a "template" -d "Generate YAML templates"
complete -c flexflow -f -n "__fish_use_subcommand" -a "tecplot" -d "Inspect and work with Tecplot PLT files"
complete -c flexflow -f -n "__fish_use_subcommand" -a "docs" -d "View documentation"

# Info command
complete -c flexflow -n "__fish_seen_subcommand_from info" -s v -l verbose -d "Enable verbose output"
complete -c flexflow -n "__fish_seen_subcommand_from info" -s h -l help -d "Show help"
complete -c flexflow -n "__fish_seen_subcommand_from info" -l examples -d "Show examples"

# New command
complete -c flexflow -n "__fish_seen_subcommand_from new" -l ref-case -d "Reference case directory" -r
complete -c flexflow -n "__fish_seen_subcommand_from new" -l problem-name -d "Problem name"
complete -c flexflow -n "__fish_seen_subcommand_from new" -l np -d "Number of processors"
complete -c flexflow -n "__fish_seen_subcommand_from new" -l freq -d "Output frequency"
complete -c flexflow -n "__fish_seen_subcommand_from new" -l from-config -d "Load from YAML file" -r
complete -c flexflow -n "__fish_seen_subcommand_from new" -l force -d "Overwrite existing directory"
complete -c flexflow -n "__fish_seen_subcommand_from new" -l list-vars -d "List available variables"
complete -c flexflow -n "__fish_seen_subcommand_from new" -l dry-run -d "Preview without creating"
complete -c flexflow -n "__fish_seen_subcommand_from new" -s v -l verbose -d "Enable verbose output"
complete -c flexflow -n "__fish_seen_subcommand_from new" -s h -l help -d "Show help"
complete -c flexflow -n "__fish_seen_subcommand_from new" -l examples -d "Show examples"

# Preview command
complete -c flexflow -n "__fish_seen_subcommand_from preview" -l node -d "Node ID to preview"
complete -c flexflow -n "__fish_seen_subcommand_from preview" -l start-time -d "Start time"
complete -c flexflow -n "__fish_seen_subcommand_from preview" -l end-time -d "End time"
complete -c flexflow -n "__fish_seen_subcommand_from preview" -s v -l verbose -d "Enable verbose output"
complete -c flexflow -n "__fish_seen_subcommand_from preview" -s h -l help -d "Show help"
complete -c flexflow -n "__fish_seen_subcommand_from preview" -l examples -d "Show examples"

# Statistics command
complete -c flexflow -n "__fish_seen_subcommand_from statistics" -l node -d "Node ID to analyze"
complete -c flexflow -n "__fish_seen_subcommand_from statistics" -s v -l verbose -d "Enable verbose output"
complete -c flexflow -n "__fish_seen_subcommand_from statistics" -s h -l help -d "Show help"
complete -c flexflow -n "__fish_seen_subcommand_from statistics" -l examples -d "Show examples"

# Plot command
complete -c flexflow -n "__fish_seen_subcommand_from plot" -l node -d "Node ID to plot"
complete -c flexflow -n "__fish_seen_subcommand_from plot" -l data-type -d "Data type" -xa "displacement force moment pressure"
complete -c flexflow -n "__fish_seen_subcommand_from plot" -l component -d "Component" -xa "x y z magnitude tx ty tz all"
complete -c flexflow -n "__fish_seen_subcommand_from plot" -l plot-type -d "Plot type" -xa "time fft traj2d traj3d"
complete -c flexflow -n "__fish_seen_subcommand_from plot" -l traj-x -d "X component" -xa "x y z magnitude"
complete -c flexflow -n "__fish_seen_subcommand_from plot" -l traj-y -d "Y component" -xa "x y z magnitude"
complete -c flexflow -n "__fish_seen_subcommand_from plot" -l traj-z -d "Z component" -xa "x y z magnitude"
complete -c flexflow -n "__fish_seen_subcommand_from plot" -l start-time -d "Start time"
complete -c flexflow -n "__fish_seen_subcommand_from plot" -l end-time -d "End time"
complete -c flexflow -n "__fish_seen_subcommand_from plot" -l start-step -d "Start timestep"
complete -c flexflow -n "__fish_seen_subcommand_from plot" -l end-step -d "End timestep"
complete -c flexflow -n "__fish_seen_subcommand_from plot" -l plot-style -d "Plot style"
complete -c flexflow -n "__fish_seen_subcommand_from plot" -l title -d "Plot title"
complete -c flexflow -n "__fish_seen_subcommand_from plot" -l xlabel -d "X-axis label"
complete -c flexflow -n "__fish_seen_subcommand_from plot" -l ylabel -d "Y-axis label"
complete -c flexflow -n "__fish_seen_subcommand_from plot" -l legend -d "Legend label"
complete -c flexflow -n "__fish_seen_subcommand_from plot" -l legend-style -d "Legend style"
complete -c flexflow -n "__fish_seen_subcommand_from plot" -l fontsize -d "Font size"
complete -c flexflow -n "__fish_seen_subcommand_from plot" -l fontname -d "Font name"
complete -c flexflow -n "__fish_seen_subcommand_from plot" -l output -d "Output file" -r
complete -c flexflow -n "__fish_seen_subcommand_from plot" -l no-display -d "Do not display plot"
complete -c flexflow -n "__fish_seen_subcommand_from plot" -l input-file -d "Load YAML config" -r
complete -c flexflow -n "__fish_seen_subcommand_from plot" -s v -l verbose -d "Enable verbose output"
complete -c flexflow -n "__fish_seen_subcommand_from plot" -s h -l help -d "Show help"
complete -c flexflow -n "__fish_seen_subcommand_from plot" -l examples -d "Show examples"

# Compare command
complete -c flexflow -n "__fish_seen_subcommand_from compare" -l node -d "Node ID to plot"
complete -c flexflow -n "__fish_seen_subcommand_from compare" -l data-type -d "Data type" -xa "displacement force moment pressure"
complete -c flexflow -n "__fish_seen_subcommand_from compare" -l component -d "Component" -xa "x y z magnitude tx ty tz all"
complete -c flexflow -n "__fish_seen_subcommand_from compare" -l plot-type -d "Plot type" -xa "time fft traj2d traj3d"
complete -c flexflow -n "__fish_seen_subcommand_from compare" -l start-time -d "Start time"
complete -c flexflow -n "__fish_seen_subcommand_from compare" -l end-time -d "End time"
complete -c flexflow -n "__fish_seen_subcommand_from compare" -l start-step -d "Start timestep"
complete -c flexflow -n "__fish_seen_subcommand_from compare" -l end-step -d "End timestep"
complete -c flexflow -n "__fish_seen_subcommand_from compare" -l title -d "Plot title"
complete -c flexflow -n "__fish_seen_subcommand_from compare" -l xlabel -d "X-axis label"
complete -c flexflow -n "__fish_seen_subcommand_from compare" -l ylabel -d "Y-axis label"
complete -c flexflow -n "__fish_seen_subcommand_from compare" -l legend -d "Legend labels"
complete -c flexflow -n "__fish_seen_subcommand_from compare" -l legend-style -d "Legend style"
complete -c flexflow -n "__fish_seen_subcommand_from compare" -l fontsize -d "Font size"
complete -c flexflow -n "__fish_seen_subcommand_from compare" -l fontname -d "Font name"
complete -c flexflow -n "__fish_seen_subcommand_from compare" -l plot-style -d "Plot styles"
complete -c flexflow -n "__fish_seen_subcommand_from compare" -l output -d "Output file" -r
complete -c flexflow -n "__fish_seen_subcommand_from compare" -l no-display -d "Do not display plot"
complete -c flexflow -n "__fish_seen_subcommand_from compare" -l subplot -d "Subplot layout"
complete -c flexflow -n "__fish_seen_subcommand_from compare" -l input-file -d "Load YAML config" -r
complete -c flexflow -n "__fish_seen_subcommand_from compare" -s v -l verbose -d "Enable verbose output"
complete -c flexflow -n "__fish_seen_subcommand_from compare" -s h -l help -d "Show help"
complete -c flexflow -n "__fish_seen_subcommand_from compare" -l examples -d "Show examples"

# Template command
complete -c flexflow -n "__fish_seen_subcommand_from template" -xa "single multi fft"
complete -c flexflow -n "__fish_seen_subcommand_from template" -l output -d "Output file" -r
complete -c flexflow -n "__fish_seen_subcommand_from template" -l force -d "Overwrite existing file"
complete -c flexflow -n "__fish_seen_subcommand_from template" -s v -l verbose -d "Enable verbose output"
complete -c flexflow -n "__fish_seen_subcommand_from template" -s h -l help -d "Show help"
complete -c flexflow -n "__fish_seen_subcommand_from template" -l examples -d "Show examples"

# Docs command
complete -c flexflow -n "__fish_seen_subcommand_from docs" -xa "main plot compare info template statistics preview tecplot"
complete -c flexflow -n "__fish_seen_subcommand_from docs" -s h -l help -d "Show help"

# Tecplot command - subcommands
complete -c flexflow -n "__fish_seen_subcommand_from tecplot; and not __fish_seen_subcommand_from info extract" -xa "info extract"

# Tecplot info subcommand
complete -c flexflow -n "__fish_seen_subcommand_from tecplot; and __fish_seen_subcommand_from info" -l basic -d "Show only basic information"
complete -c flexflow -n "__fish_seen_subcommand_from tecplot; and __fish_seen_subcommand_from info" -l variables -d "Show variable names"
complete -c flexflow -n "__fish_seen_subcommand_from tecplot; and __fish_seen_subcommand_from info" -l zones -d "Show zone information"
complete -c flexflow -n "__fish_seen_subcommand_from tecplot; and __fish_seen_subcommand_from info" -l checks -d "Show consistency checks"
complete -c flexflow -n "__fish_seen_subcommand_from tecplot; and __fish_seen_subcommand_from info" -l stats -d "Show statistics"
complete -c flexflow -n "__fish_seen_subcommand_from tecplot; and __fish_seen_subcommand_from info" -l detailed -d "Show detailed statistics"
complete -c flexflow -n "__fish_seen_subcommand_from tecplot; and __fish_seen_subcommand_from info" -l sample-file -d "Analyze specific timestep"
complete -c flexflow -n "__fish_seen_subcommand_from tecplot; and __fish_seen_subcommand_from info" -s v -l verbose -d "Enable verbose output"
complete -c flexflow -n "__fish_seen_subcommand_from tecplot; and __fish_seen_subcommand_from info" -s h -l help -d "Show help"

# Tecplot extract subcommand
complete -c flexflow -n "__fish_seen_subcommand_from tecplot; and __fish_seen_subcommand_from extract" -l variables -d "Variables to extract (comma-separated)"
complete -c flexflow -n "__fish_seen_subcommand_from tecplot; and __fish_seen_subcommand_from extract" -l zone -d "Zone name to extract from"
complete -c flexflow -n "__fish_seen_subcommand_from tecplot; and __fish_seen_subcommand_from extract" -l timestep -d "Timestep to extract"
complete -c flexflow -n "__fish_seen_subcommand_from tecplot; and __fish_seen_subcommand_from extract" -l output-file -d "Output file path" -r
complete -c flexflow -n "__fish_seen_subcommand_from tecplot; and __fish_seen_subcommand_from extract" -l xmin -d "Minimum X coordinate"
complete -c flexflow -n "__fish_seen_subcommand_from tecplot; and __fish_seen_subcommand_from extract" -l xmax -d "Maximum X coordinate"
complete -c flexflow -n "__fish_seen_subcommand_from tecplot; and __fish_seen_subcommand_from extract" -l ymin -d "Minimum Y coordinate"
complete -c flexflow -n "__fish_seen_subcommand_from tecplot; and __fish_seen_subcommand_from extract" -l ymax -d "Maximum Y coordinate"
complete -c flexflow -n "__fish_seen_subcommand_from tecplot; and __fish_seen_subcommand_from extract" -l zmin -d "Minimum Z coordinate"
complete -c flexflow -n "__fish_seen_subcommand_from tecplot; and __fish_seen_subcommand_from extract" -l zmax -d "Maximum Z coordinate"
complete -c flexflow -n "__fish_seen_subcommand_from tecplot; and __fish_seen_subcommand_from extract" -s v -l verbose -d "Enable verbose output"
complete -c flexflow -n "__fish_seen_subcommand_from tecplot; and __fish_seen_subcommand_from extract" -s h -l help -d "Show help"
complete -c flexflow -n "__fish_seen_subcommand_from tecplot; and __fish_seen_subcommand_from extract" -s h -l help -d "Show help"
'''


def generate_completion_script(shell='bash'):
    """
    Generate shell completion script
    
    Parameters:
    -----------
    shell : str
        Shell type: 'bash', 'zsh', or 'fish'
    
    Returns:
    --------
    str
        Completion script content
    """
    if shell == 'bash':
        return BASH_COMPLETION_SCRIPT
    elif shell == 'zsh':
        return ZSH_COMPLETION_SCRIPT
    elif shell == 'fish':
        return FISH_COMPLETION_SCRIPT
    else:
        raise ValueError(f"Unsupported shell: {shell}")


def get_completion_install_path(shell='bash'):
    """
    Get the installation path for completion scripts
    
    Parameters:
    -----------
    shell : str
        Shell type: 'bash', 'zsh', or 'fish'
    
    Returns:
    --------
    Path
        Installation path for the completion script
    """
    home = Path.home()
    
    if shell == 'bash':
        # Always use user directory to avoid permission issues
        completion_dir = home / '.bash_completion.d'
        completion_dir.mkdir(exist_ok=True)
        return completion_dir / 'flexflow'
    
    elif shell == 'zsh':
        # Use user's zsh completion directory
        zsh_completion_dir = home / '.zsh' / 'completion'
        zsh_completion_dir.mkdir(parents=True, exist_ok=True)
        return zsh_completion_dir / '_flexflow'
    
    elif shell == 'fish':
        # Use fish user completions directory
        fish_completion_dir = home / '.config' / 'fish' / 'completions'
        fish_completion_dir.mkdir(parents=True, exist_ok=True)
        return fish_completion_dir / 'flexflow.fish'
    
    else:
        raise ValueError(f"Unsupported shell: {shell}")


def install_completion(shell='bash', verbose=False):
    """
    Install shell completion for the specified shell
    
    Parameters:
    -----------
    shell : str
        Shell type: 'bash', 'zsh', or 'fish'
    verbose : bool
        Enable verbose output
    
    Returns:
    --------
    bool
        True if installation successful, False otherwise
    """
    try:
        script = generate_completion_script(shell)
        install_path = get_completion_install_path(shell)
        
        # Write completion script
        install_path.parent.mkdir(parents=True, exist_ok=True)
        install_path.write_text(script)
        
        if verbose:
            print(f"Installed {shell} completion to: {install_path}")
        
        # Add instructions for enabling completion
        if shell == 'bash':
            bash_rc = Path.home() / '.bashrc'
            completion_source = f"\n# FlexFlow completion\n"
            
            if not install_path.parent.name == 'bash_completion.d':
                completion_source += f"[[ -f {install_path} ]] && source {install_path}\n"
                
                # Check if already in .bashrc
                if bash_rc.exists():
                    bashrc_content = bash_rc.read_text()
                    if str(install_path) not in bashrc_content:
                        if verbose:
                            print(f"\nAdd this to your {bash_rc}:")
                            print(completion_source)
        
        elif shell == 'zsh':
            zsh_rc = Path.home() / '.zshrc'
            completion_dir = install_path.parent
            completion_source = f"\n# FlexFlow completion\nfpath=({completion_dir} $fpath)\nautoload -Uz compinit && compinit\n"
            
            if zsh_rc.exists():
                zshrc_content = zsh_rc.read_text()
                if str(completion_dir) not in zshrc_content:
                    if verbose:
                        print(f"\nAdd this to your {zsh_rc}:")
                        print(completion_source)
        
        elif shell == 'fish':
            # Fish automatically loads completions from this directory
            if verbose:
                print("Fish will automatically load completions on next shell restart")
        
        return True
    
    except PermissionError as e:
        print(f"Error: Permission denied writing to {install_path.parent}")
        print(f"The completion script will be saved to a user directory instead.")
        return False
    except Exception as e:
        print(f"Error installing {shell} completion: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return False


def uninstall_completion(shell='bash', verbose=False):
    """
    Uninstall shell completion for the specified shell
    
    Parameters:
    -----------
    shell : str
        Shell type: 'bash', 'zsh', or 'fish'
    verbose : bool
        Enable verbose output
    
    Returns:
    --------
    bool
        True if uninstallation successful, False otherwise
    """
    try:
        install_path = get_completion_install_path(shell)
        
        if install_path.exists():
            install_path.unlink()
            if verbose:
                print(f"Removed {shell} completion from: {install_path}")
            return True
        else:
            if verbose:
                print(f"No {shell} completion found at: {install_path}")
            return False
    
    except Exception as e:
        print(f"Error uninstalling {shell} completion: {e}")
        return False


def detect_shell():
    """
    Detect the current shell
    
    Returns:
    --------
    str
        Shell name ('bash', 'zsh', or 'fish'), or None if unknown
    """
    shell = os.environ.get('SHELL', '')
    
    if 'bash' in shell:
        return 'bash'
    elif 'zsh' in shell:
        return 'zsh'
    elif 'fish' in shell:
        return 'fish'
    else:
        return None


if __name__ == '__main__':
    # Test script generation
    import sys
    
    if len(sys.argv) > 1:
        shell_type = sys.argv[1]
        print(generate_completion_script(shell_type))
    else:
        print("Usage: python completion.py [bash|zsh|fish]")
