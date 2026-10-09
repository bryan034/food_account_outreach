<!-- LOVABLE:BEGIN -->
> [!IMPORTANT]
> This project is connected to [Lovable](https://lovable.dev). Avoid rewriting
> published git history — force pushing, or rebasing/amending/squashing commits
> that are already pushed — as it rewrites history on Lovable's side and the
> user will likely lose their project history.
>
> Commits you push to the connected branch sync back to Lovable and show up in
> the editor, so keep the branch in a working state.
<!-- LOVABLE:END -->

## Frontend architecture
- Keep all business API operations behind the typed ApiClient interface; this lets FastAPI and the isolated in-memory demo implement the same contract without adding a backend.
- Keep public URL/mode configuration in browser storage only; persistent application records remain owned by FastAPI, and demo records are ephemeral.
- Use separate TanStack routes for Discover, Outreach and Settings with a shared workspace provider and shell; this preserves direct navigation and route-specific metadata.
- Cache restaurant lookups by local ID in the connected client; outreach records do not contain restaurant names.
- Enforce status action visibility from the shared transition map while allowing the backend to reject changes; the client never substitutes its decisions for FastAPI.
