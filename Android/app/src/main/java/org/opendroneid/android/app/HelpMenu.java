package org.opendroneid.android.app;

import android.os.Bundle;
import android.text.method.LinkMovementMethod;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.core.text.HtmlCompat;
import androidx.fragment.app.DialogFragment;

import org.opendroneid.android.R;

public class HelpMenu extends DialogFragment {

    static HelpMenu newInstance() { return new HelpMenu(); }

    @Override @Nullable
    public View onCreateView(@NonNull LayoutInflater inflater, @Nullable ViewGroup container,
                             @Nullable Bundle savedInstanceState) {

        View view = inflater.inflate(R.layout.help_text, container, false);

        TextView bluetoothHelpView = view.findViewById(R.id.bluetoothHelpText);
        String bluetoothLinkText = getString(R.string.bluetoothHelp);
        bluetoothHelpView.setText(HtmlCompat.fromHtml(bluetoothLinkText, HtmlCompat.FROM_HTML_MODE_LEGACY));

        TextView beaconHelpView = view.findViewById(R.id.beaconHelpText);
        String beaconLinkText = getString(R.string.beaconHelp);
        beaconHelpView.setText(HtmlCompat.fromHtml(beaconLinkText, HtmlCompat.FROM_HTML_MODE_LEGACY));
        beaconHelpView.setMovementMethod(LinkMovementMethod.getInstance());

        TextView nanHelpView = view.findViewById(R.id.nanHelpText);
        String nanLinkText = getString(R.string.nanHelp);
        nanHelpView.setText(HtmlCompat.fromHtml(nanLinkText, HtmlCompat.FROM_HTML_MODE_LEGACY));
        return view;
    }
}
