#!/bin/bash

# --- Color Definitions ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# --- Cross-platform sed compatibility ---
if [[ "$(uname)" == "Darwin" ]]; then
  SED_CMD=("sed" "-i" "")
else
  SED_CMD=("sed" "-i")
fi

# --- Error Handling Function ---
exit_if() {
  local exit_code=$1
  local msg=$2
  if [[ $exit_code -ne 0 ]]; then
    if [[ -n "$msg" ]]; then
      echo -e "${RED}[ERROR]${NC} $msg" >&2
    fi
    exit $exit_code
  fi
}

# --- Path Safety Validation ---
validate_path() {
  local path_var=$1
  if [[ -z "${!path_var}" || "${!path_var}" == "/" ]]; then
    echo -e "${RED}[ERROR]${NC} Unsafe path value for $path_var: '${!path_var}'" >&2
    exit 1
  fi
}

# --- Proto Compilation Function ---
compile_protos() {
  local proto_submodule_dir=$1
  local intermediate_dir=$2
  
  echo -e "${GREEN}[INFO]${NC} Finding proto files..."
  local protofiles=$(find "$proto_submodule_dir" -name '*.proto') 
  exit_if $? "Failed to find proto files in $proto_submodule_dir"

  echo -e "${GREEN}[INFO]${NC} Compiling Python interfaces..."
  python3 -m grpc_tools.protoc \
    -I "$proto_submodule_dir" \
    --python_out="$intermediate_dir" \
    --grpc_python_out="$intermediate_dir" \
    $protofiles
  exit_if $? "Protoc compilation failed"
}

# --- Import Path Fix Function ---
fix_import_paths() {
  local dir_to_fix=$1
  echo -e "${GREEN}[INFO]${NC} Fixing import paths..."
  
  find "$dir_to_fix" -name '*.py' -exec "${SED_CMD[@]}" \
    's/^from dapplink import/from services.savourrpc import/g' {} +
  exit_if $? "sed command failed"

  # Cleanup backup files on macOS
  find "$dir_to_fix" -name '*.bak' -delete 2>/dev/null
}

# --- File Sync Function ---
sync_generated_files() {
  local src_dir=$1
  local dest_dir=$2
  shift 2
  local modules=("$@")
  
  declare -a synced_files=("__init__.py")
  
  for module in "${modules[@]}"; do
    echo -e "${GREEN}[INFO]${NC} Syncing $module..."
    
    # Sync _pb2.py
    local src_pb2="${src_dir}/${module}_pb2.py"
    local dest_pb2="${dest_dir}/${module}_pb2.py"
    if [[ -f "$src_pb2" ]]; then
      cp -p "$src_pb2" "$dest_pb2"
      exit_if $? "Failed to copy $src_pb2"
      synced_files+=("${module}_pb2.py")
    fi

    # Sync _pb2_grpc.py 
    local src_grpc="${src_dir}/${module}_pb2_grpc.py"
    local dest_grpc="${dest_dir}/${module}_pb2_grpc.py"
    if [[ -f "$src_grpc" ]]; then
      cp -p "$src_grpc" "$dest_grpc"
      exit_if $? "Failed to copy $src_grpc"
      synced_files+=("${module}_pb2_grpc.py")
    fi
  done

  # Clean non-specified files
  echo -e "${GREEN}[INFO]${NC} Cleaning old files..."
  find "$dest_dir" -maxdepth 1 -type f \
    ! -name '__init__.py' \
    ! -name '*_pb2.py' \
    ! -name '*_pb2_grpc.py' \
    -exec rm -f {} +
}

# --- Main Execution ---
main() {
  # --- Configuration ---
  local PROTO_SUBMODULE_DIR="external/dapplink-proto"
  local PROTO_SRC_DIR="${PROTO_SUBMODULE_DIR}/dapplink"
  local PYTHON_INTERMEDIATE_DIR="python_build_temp"
  local PYTHON_FINAL_DIR="services/savourrpc"
  local TARGET_MODULES=("chaineye" "common" "market" "wallet")

  # --- Path Validation ---
  for path in PROTO_SUBMODULE_DIR PYTHON_INTERMEDIATE_DIR PYTHON_FINAL_DIR; do
    validate_path "$path"
  done

  # --- Submodule Check ---
  if [[ ! -d "$PROTO_SUBMODULE_DIR" ]] || [[ -z "$(ls -A "$PROTO_SUBMODULE_DIR")" ]]; then
    echo -e "${RED}[ERROR]${NC} Proto submodule missing. Run: git submodule update --init --recursive" >&2
    exit 1
  fi

  # --- Cleanup ---
  echo -e "${GREEN}[INFO]${NC} Initializing build environment..."
  rm -rf "$PYTHON_INTERMEDIATE_DIR"
  mkdir -p "$PYTHON_INTERMEDIATE_DIR" "$PYTHON_FINAL_DIR"

  # --- Compilation ---
  compile_protos "$PROTO_SUBMODULE_DIR" "$PYTHON_INTERMEDIATE_DIR"
  local protoc_output_dir="${PYTHON_INTERMEDIATE_DIR}/dapplink"
  
  # --- Post-processing ---
  touch "${protoc_output_dir}/__init__.py"
  fix_import_paths "$protoc_output_dir"

  # --- Final Sync ---
  sync_generated_files "$protoc_output_dir" "$PYTHON_FINAL_DIR" "${TARGET_MODULES[@]}"

  # --- Finalization ---
  echo -e "${GREEN}[INFO]${NC} Cleaning intermediates..."
  rm -rf "$PYTHON_INTERMEDIATE_DIR"
  echo -e "${GREEN}[SUCCESS]${NC} Proto compilation completed"
}

# --- Execute Main ---
main