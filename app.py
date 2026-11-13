    # ========================================================
    # REGENERATE LAST ANSWER — FIXED
    # ========================================================

    if st.session_state.get("last_prompt"):
        if st.button("🔄 Regenerate last answer", use_container_width=True):

            chat_id = st.session_state.chat_id
            user_id = st.session_state.user_id

            try:
                with st.spinner("Generating a new response..."):

                    history = st.session_state.messages[:-1]

                    answer, provider = ask_ai(
                        st.session_state.last_prompt,
                        history
                    )

                    # Remove old assistant response from database
                    remove_last_assistant_message(
                        chat_id,
                        user_id
                    )

                    # Remove old assistant response from session
                    if (
                        st.session_state.messages
                        and st.session_state.messages[-1]["role"] == "assistant"
                    ):
                        st.session_state.messages.pop()

                    # Save new response
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer
                    })

                    save_message(
                        chat_id,
                        "assistant",
                        answer
                    )

                    st.session_state.last_response = answer

                    st.success("New response generated!")
                    st.rerun()

            except Exception as e:
                st.error(f"Regeneration failed: {e}")
