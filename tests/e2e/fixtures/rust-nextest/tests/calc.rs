use calc::is_adult;

#[test]
fn adult_at_18() {
    assert!(is_adult(18));
}

#[test]
fn adult_at_30() {
    assert!(is_adult(30));
}
