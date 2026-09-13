package dev.pex.crashapp;

import android.app.Activity;
import android.os.Bundle;
import android.text.InputType;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.net.HttpURLConnection;
import java.net.URL;

public final class MainActivity extends Activity {
  private LinearLayout page;

  @Override public void onCreate(Bundle state) {
    super.onCreate(state);
    showHome();
  }

  private TextView text(String value) {
    TextView view = new TextView(this);
    view.setText(value);
    view.setTextSize(20);
    view.setPadding(24, 24, 24, 24);
    return view;
  }

  private Button button(String label, View.OnClickListener action) {
    Button button = new Button(this);
    button.setText(label);
    button.setContentDescription(label);
    button.setOnClickListener(action);
    return button;
  }

  private void showHome() {
    page = new LinearLayout(this);
    page.setOrientation(LinearLayout.VERTICAL);
    page.setPadding(24, 24, 24, 24);
    page.addView(text("PEX fixture " + FixtureVersion.NAME));
    EditText plain = new EditText(this);
    plain.setHint("Plain text input");
    plain.setContentDescription("Plain text input");
    page.addView(plain);
    EditText password = new EditText(this);
    password.setHint("Password input");
    password.setContentDescription("Password input");
    password.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
    page.addView(password);
    page.addView(button("Change screen", v -> showSecond()));
    page.addView(button("Crash", v -> { throw new IllegalStateException("PEX fixture crash " + FixtureVersion.NAME); }));
    page.addView(button("Freeze", v -> {
      long until = System.currentTimeMillis() + 30000;
      while (System.currentTimeMillis() < until) { /* Intentional main-thread ANR fixture. */ }
    }));
    String probe = getIntent().getStringExtra("probe_url");
    if (probe != null && probe.startsWith("https://")) page.addView(button("HTTPS probe", v -> probe(probe)));
    setContentView(page);
  }

  private void showSecond() {
    page.removeAllViews();
    page.addView(text("Changed screen " + FixtureVersion.NAME));
    page.addView(button("Back home", v -> showHome()));
  }

  private void probe(String endpoint) {
    TextView result = text("Probe running");
    page.addView(result);
    new Thread(() -> {
      String message;
      try {
        HttpURLConnection connection = (HttpURLConnection) new URL(endpoint).openConnection();
        connection.setConnectTimeout(5000);
        connection.setReadTimeout(5000);
        message = "Probe HTTP " + connection.getResponseCode();
        connection.disconnect();
      } catch (Exception error) { message = "Probe failed: " + error.getClass().getSimpleName(); }
      String finalMessage = message;
      runOnUiThread(() -> result.setText(finalMessage));
    }).start();
  }
}
