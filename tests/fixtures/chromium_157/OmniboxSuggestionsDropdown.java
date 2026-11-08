class OmniboxSuggestionsDropdown {
    class SuggestionLayoutScrollListener extends LinearLayoutManager {
        private boolean mCurrentGestureAffectedKeyboardState;

        @Override
        public void onLayoutChildren(RecyclerView.Recycler recycler, RecyclerView.State state) {
            if (OmniboxFeatures.sResetSuggestionsScroll.isEnabled()) {
                scrollToPositionWithOffset(0, 0);
            }
            super.onLayoutChildren(recycler, state);
        }

        /* package */ void updateVisualScrollState() {
            if (!mIsScrolledToTop) return;
            postOnAnimation(() -> scrollToPositionWithOffset(0, 0));
        }

        /**
         * Reset the internal scroll tracker. This needs to be called either when the
         * SuggestionsDropdown is hidden or shown again to reflect either the end of the current or
         * beginning of the next interaction session.
         */
        /* package */ void resetScrollState() {
            mIsScrolledToTop = true;
        }

    }

    private void handleSelectionChange() {
        boolean isParked = true;
        if (isParked) {
            mLayoutScrollListener.scrollToPositionWithOffset(0, 0);
        }
    }

    public void resetSelection() {
        mLayoutScrollListener.scrollToPositionWithOffset(0, 0);
        mSelectionController.reset();
    }
}
