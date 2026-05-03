



void setup() {

  Serial.begin(115200);
  Serial1.begin(9600);
}

void loop() {
  // put your main code here, to run repeatedly:

  if(Serial1.available()){
    Serial.println(Serial1.read());
  }

}
