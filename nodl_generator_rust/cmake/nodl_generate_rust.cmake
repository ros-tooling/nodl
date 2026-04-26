# nodl_generate_rust(target nodl_file)
#
# Generates a Rust source file (<target>_nodl.rs) from a NoDL YAML file.
# The file is written to ${CMAKE_CURRENT_BINARY_DIR}/nodl_generated/ and a
# CMake custom target is created so it rebuilds when the NoDL file changes.
#
# The generated file is a self-contained Rust module.  Add it to your crate
# by including it from a build.rs-aware location or placing it via a
# configure step:
#
#   nodl_generate_rust(my_node nodl/my_node.nodl.yaml)
#
# Then in your crate's build.rs:
#   println!("cargo:rerun-if-changed=nodl/my_node.nodl.yaml");
#   // The generated file is at the path printed by the cmake target.
#
# Or simply declare a mod in src/lib.rs and point rustc at the build dir via
# a RUSTFLAGS include path (see nodl_generator_rust documentation).
#
function(nodl_generate_rust target nodl_file)
  get_filename_component(_nodl_abs "${nodl_file}" ABSOLUTE
    BASE_DIR "${CMAKE_CURRENT_SOURCE_DIR}")

  if(NOT EXISTS "${_nodl_abs}")
    message(WARNING "nodl_generate_rust: NoDL file not found at configure time: ${_nodl_abs}")
  endif()

  set(_out_dir "${CMAKE_CURRENT_BINARY_DIR}/nodl_generated")
  file(MAKE_DIRECTORY "${_out_dir}")
  set(_rs_out "${_out_dir}/${target}_nodl.rs")

  add_custom_command(
    OUTPUT "${_rs_out}"
    COMMAND "${Python3_EXECUTABLE}"
      "${_NODL_GENERATOR_RUST_SCRIPT}"
      --nodl-file "${_nodl_abs}"
      --output-dir "${_out_dir}"
      --target-name "${target}"
      --templates-dir "${_NODL_GENERATOR_RUST_TEMPLATES_DIR}"
    DEPENDS
      "${_nodl_abs}"
      "${_NODL_GENERATOR_RUST_SCRIPT}"
    COMMENT "nodl_generate_rust: generating ${target}_nodl.rs from ${nodl_file}"
    VERBATIM
  )

  add_custom_target(${target}_nodl_rs ALL DEPENDS "${_rs_out}")

  # Export the generated file path so the Rust build.rs can find it.
  set(NODL_GENERATED_RS_${target} "${_rs_out}" PARENT_SCOPE)
endfunction()
