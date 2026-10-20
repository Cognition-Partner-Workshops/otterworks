package com.otterworks.commission.splits;

import java.util.List;

/**
 * Body sent by the COMMISSION_PKG.set_commission_splits delegate. {@code splits}
 * is the split_alloc_tab in collection order, or null for a NULL collection.
 */
public record SetSplitsRequest(List<SplitAllocation> splits, String actor) {
}
