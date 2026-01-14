# Palette's Journal

## 2024-05-22 - Initial Setup
**Learning:** Streamlit apps require different UX strategies than React apps. Standard HTML/CSS tweaks are harder to inject cleanly.
**Action:** Focus on Streamlit's native parameters (like `help=`, `placeholder=`, `on_click=`) and use `st.markdown` carefully for styling.

## 2025-05-22 - Tooltips in Streamlit
**Learning:** Streamlit's `help` parameter is the most robust way to add accessibility context (tooltips) to buttons, as it renders natively and works across themes without custom CSS.
**Action:** Always check `st.button`, `st.text_input`, and `st.popover` for `help=` opportunities before attempting custom HTML injection.

## 2025-05-23 - Empty States in Lists
**Learning:** Iterating directly over lists without checking for emptiness (e.g., `for item in load_items():`) is a common pattern that misses the opportunity for helpful empty states. Users are left wondering if the feature is broken or just empty.
**Action:** Always capture list results into a variable first, check `if not list:` to render an `st.info` or `st.caption` guidance message, and then iterate.

## 2025-05-23 - Destructive Action Confirmation
**Learning:** Destructive actions like "Clear notes" in Streamlit require manual state management for confirmation, as `st.button` doesn't support native confirmation dialogs (unlike `window.confirm` in JS).
**Action:** Use a session state toggle to swap the trigger button with a "Confirm/Cancel" UI within the same container to prevent accidental data loss.
## 2025-05-15 - Streamlit Input Context
**Learning:** Adding placeholders and help tooltips to complex inputs like 'Root Cause' significantly reduces user cognitive load by providing immediate examples of expected input format.
**Action:** Always check  and  calls in critical workflows (like Sprint or Settings) for missing  and GNU bash, version 5.2.21(1)-release (x86_64-pc-linux-gnu)
These shell commands are defined internally.  Type `help' to see this list.
Type `help name' to find out more about the function `name'.
Use `info bash' to find out more about the shell in general.
Use `man -k' or `info' to find out more about commands not in this list.

A star (*) next to a name means that the command is disabled.

 job_spec [&]                            history [-c] [-d offset] [n] or hist>
 (( expression ))                        if COMMANDS; then COMMANDS; [ elif C>
 . filename [arguments]                  jobs [-lnprs] [jobspec ...] or jobs >
 :                                       kill [-s sigspec | -n signum | -sigs>
 [ arg... ]                              let arg [arg ...]
 [[ expression ]]                        local [option] name[=value] ...
 alias [-p] [name[=value] ... ]          logout [n]
 bg [job_spec ...]                       mapfile [-d delim] [-n count] [-O or>
 bind [-lpsvPSVX] [-m keymap] [-f file>  popd [-n] [+N | -N]
 break [n]                               printf [-v var] format [arguments]
 builtin [shell-builtin [arg ...]]       pushd [-n] [+N | -N | dir]
 caller [expr]                           pwd [-LP]
 case WORD in [PATTERN [| PATTERN]...)>  read [-ers] [-a array] [-d delim] [->
 cd [-L|[-P [-e]] [-@]] [dir]            readarray [-d delim] [-n count] [-O >
 command [-pVv] command [arg ...]        readonly [-aAf] [name[=value] ...] o>
 compgen [-abcdefgjksuv] [-o option] [>  return [n]
 complete [-abcdefgjksuv] [-pr] [-DEI]>  select NAME [in WORDS ... ;] do COMM>
 compopt [-o|+o option] [-DEI] [name .>  set [-abefhkmnptuvxBCEHPT] [-o optio>
 continue [n]                            shift [n]
 coproc [NAME] command [redirections]    shopt [-pqsu] [-o] [optname ...]
 declare [-aAfFgiIlnrtux] [name[=value>  source filename [arguments]
 dirs [-clpv] [+N] [-N]                  suspend [-f]
 disown [-h] [-ar] [jobspec ... | pid >  test [expr]
 echo [-neE] [arg ...]                   time [-p] pipeline
 enable [-a] [-dnps] [-f filename] [na>  times
 eval [arg ...]                          trap [-lp] [[arg] signal_spec ...]
 exec [-cl] [-a name] [command [argume>  true
 exit [n]                                type [-afptP] name [name ...]
 export [-fn] [name[=value] ...] or ex>  typeset [-aAfFgiIlnrtux] name[=value>
 false                                   ulimit [-SHabcdefiklmnpqrstuvxPRT] [>
 fc [-e ename] [-lnr] [first] [last] o>  umask [-p] [-S] [mode]
 fg [job_spec]                           unalias [-a] name [name ...]
 for NAME [in WORDS ... ] ; do COMMAND>  unset [-f] [-v] [-n] [name ...]
 for (( exp1; exp2; exp3 )); do COMMAN>  until COMMANDS; do COMMANDS-2; done
 function name { COMMANDS ; } or name >  variables - Names and meanings of so>
 getopts optstring name [arg ...]        wait [-fn] [-p var] [id ...]
 hash [-lr] [-p pathname] [-dt] [name >  while COMMANDS; do COMMANDS-2; done
 help [-dms] [pattern ...]               { COMMANDS ; } attributes during UX reviews.
## 2025-05-15 - Streamlit Input Context
**Learning:** Adding placeholders and help tooltips to complex inputs like 'Root Cause' significantly reduces user cognitive load by providing immediate examples of expected input format.
**Action:** Always check `st.text_input` and `st.text_area` calls in critical workflows (like Sprint or Settings) for missing `placeholder` and `help` attributes during UX reviews.
