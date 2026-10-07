from automate_food_places_outreach.services.website_enrichment import extract_contacts


def test_contacts_keep_sources_and_deduplicate_profile_links():
    contacts = extract_contacts(
        '''
        <a href="mailto:hello@EXAMPLE.com?subject=Collaboration">Email</a>
        <a href="mailto:hello@example.com">Email again</a>
        <a href="https://instagram.com/examplecafe/?utm_source=website">Instagram</a>
        <a href="https://www.instagram.com/examplecafe/">Instagram again</a>
        <a href="//www.tiktok.com/@examplecafe">TikTok</a>
        ''',
        "https://example.com/contact",
    )
    assert [(contact.contact_type, contact.value) for contact in contacts] == [
        ("email", "hello@example.com"),
        ("instagram", "examplecafe"),
        ("tiktok", "examplecafe"),
    ]
    assert all(contact.source_url == "https://example.com/contact" for contact in contacts)
    assert all(not contact.verified and not contact.usable for contact in contacts)
    assert contacts[1].direct_url == "https://www.instagram.com/examplecafe/"


def test_non_contacts_and_spoofed_domains_are_ignored():
    contacts = extract_contacts(
        '''
        <a href="/contact">Contact page</a>
        <a href="https://instagram.com.evil.example/cafe">Spoof</a>
        <a href="https://instagram.com@evil.example/cafe">User info spoof</a>
        <a href="https://instagram.com/p/post123/">Post</a>
        <a href="https://instagram.com/explore/">Explore</a>
        <a href="https://tiktok.com/@cafe/video/123">Video</a>
        <a href="mailto:not-an-email">Broken email</a>
        <a href="https://instagram.com:bad/cafe">Invalid port</a>
        <a href="https://wa.me/123456789">WhatsApp</a>
        ''',
        "https://example.com",
    )
    assert contacts == []
